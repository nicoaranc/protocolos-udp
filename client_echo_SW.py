#!/usr/bin/python3
# Echo client program
# Version con dos threads: uno lee de stdin hacia el socket y el otro al revés
import jsockets
import sys, threading
import time


# VARIABLES GLOBALES

mutex_cond = threading.Condition()
recibidos = -1
enviados = 0
error_envio = 0
error_recep = 0


# RECEPTOR

def Rdr(s, size):
    global recibidos, error_recep
    while True:
        try:
            total = s.recv(size+2) # Recibe el paquete
            paquete = total[0:2] # Extrae el numero del paquete
            data=total[2:len(total)] # Extrae la data del paquete
        except:
            data = None
        if not data:
            mutex_cond.acquire()
            paquete = int.from_bytes(paquete, byteorder='big')
            recibidos = paquete%65536
            mutex_cond.notify()
            mutex_cond.release()
            break
        mutex_cond.acquire()
        paquete = int.from_bytes(paquete, byteorder='big')

        # Verifica que el paquete que llego corresponde al esperado
        if paquete-recibidos == 1: 
            sys.stdout.buffer.write(data) # Escribe el contenido del paquete
            recibidos = paquete%65536 # Actualiza el numero de paquete recibido
            mutex_cond.notify() # Notifica que el paquete llego
        else:
            # No llego el paquete esperado, error de recepcion
            error_recep += 1
        mutex_cond.release()
           

if len(sys.argv) != 4:
    print('Use: '+sys.argv[0]+' host port')
    sys.exit(1)

s = jsockets.socket_udp_connect(sys.argv[2], sys.argv[3])
if s is None:
    print('could not open socket')
    sys.exit(1)

tamaño = int(sys.argv[1])


# Creo thread que lee desde el socket hacia stdout:
newthread = threading.Thread(target=Rdr, args=(s,tamaño, ))
newthread.start()

# En este otro thread leo desde stdin hacia socket:
data=sys.stdin.buffer.read(tamaño)
timeout = 0.5
while(data):

    tiempo_inicio = time.time()
    mutex_cond.acquire()

    while (enviados != recibidos): # Mientras no llegue el paquete a enviar
        error_envio += 1 # Por cada ciclo aumento en 1 el error de envio 
        mutex_cond.release()
        tiempo_inicio = time.time() # Guardo el tiempo de envio
        num_paquete = enviados.to_bytes(2, byteorder='big') # Transformo el numero a bytes
        data = num_paquete+data # Junto el contenido con el numero del paquete
        s.send(data) # Mando el paquete
        mutex_cond.acquire()
        mutex_cond.wait(timeout=timeout) # Espero el timeout

    # Llega el paquete esperado
    rtt = time.time()-tiempo_inicio # Guardo el rtt
    timeout = rtt * 3 # Actualizo el timeout

    data=sys.stdin.buffer.read(tamaño)
    if data:
        enviados += 1
        enviados %= 65536

    mutex_cond.release()

error_envio = error_envio - enviados # Se le restan los paquetes que efectivamente llegaron

enviados += 1
mutex_cond.acquire()
while enviados != recibidos: # Manejo el EOF
    s.send(enviados.to_bytes(2, byteorder='big')) 
    mutex_cond.wait(timeout)
mutex_cond.release()
s.close()

sys.stderr.write(f'Usando: pack: {tamaño}\n')
sys.stderr.write(f'Errores de envío: {error_envio}\n')
sys.stderr.write(f'Errores de recepción: {error_recep}\n')