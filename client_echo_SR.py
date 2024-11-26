#!/usr/bin/python3
# Echo client program
# Version con dos threads: uno lee de stdin hacia el socket y el otro al revés
import jsockets
import sys, threading
import time
from queue import PriorityQueue


# La clase package almacena información importante de cada paquete

class Package:

    def __init__(self, data, number, time):

        self.data = data        # el contenido del paquete
        self.number = number    # el número del paquete
        self.status = 0         # el estado del paquete (recibido?)
        self.time = time        # tiempo en el que se envió
        self.time_recibido = 0  # tiempo en el que llegó


    # Actualiza el estado del paquete junto con su tiempo de llegada
    def received(self, tiempo):
        self.status = 1
        self.time_recibido = tiempo

    
# La clase window almacena información importante de las ventanas

class Window:

    def __init__(self, size):
        self.size = size       # tamaño de la ventana
        self.anterior = -1     # último paquete recibido antes de la ventana
        self.primero = 0       # primer paquete a recibir del rango
        self.ultimo = size-1   # último paquete a recibir del rango
        self.list = []         # lista de la ventana



# Variables globales

error_envio = 0
error_recep = 0
mutex_cond = threading.Condition()
enviado = 0
terminado = 0



# Receptor

def Rdr(s, size):
    global arreglo, error_recep, recepcion
    while True:
        try:
            total = s.recv(size+2)
            paquete = total[0:2]
            data=total[2:len(total)] 
        except:
            data = None
        if not data:
            arreglo.list[0].received(time.time())
            break
        mutex_cond.acquire()
        paquete = int.from_bytes(paquete, byteorder='big')
        # Manejo de la recepción de paquetes
        if recepcion.primero <= paquete and paquete <= recepcion.ultimo and recepcion.primero < recepcion.ultimo:
            # seteo el estado del paquete
            index = paquete - recepcion.primero
            recepcion.list[index] = 1
            arreglo.list[index].received(time.time())
            # Si llegó el primer paquete esperado, se actualiza la ventana
            if (recepcion.primero % 65536) == (paquete % 65536):
                updateWindowRec(recepcion, arreglo)
                mutex_cond.notify()
        elif recepcion.primero > recepcion.ultimo:
            if paquete >= recepcion.primero:
                # seteo el estado del paquete
                index = paquete - recepcion.primero
                recepcion.list[index] = 1
                arreglo.list[index].received(time.time())
                # Si llegó el primer paquete esperado, se actualiza la ventana
                if (recepcion.primero % 65536) == (paquete % 65536):
                    updateWindowRec(recepcion, arreglo)
                    mutex_cond.notify()
            elif paquete <= recepcion.ultimo:
                # seteo el estado del paquete
                index = 65536 - recepcion.primero + paquete
                recepcion.list[index] = 1
                arreglo.list[index].received(time.time())
                # Si llegó el primer paquete esperado, se actualiza la ventana
                if (recepcion.primero % 65536) == (paquete % 65536):
                    updateWindowRec(recepcion, arreglo)
                    mutex_cond.notify()
            else:
                error_recep += 1
        else:
            error_recep += 1
        mutex_cond.release()



# Actualiza la ventana de recepción y de emisión

def updateWindowRec(receptor: Window, emisor: Window):
    if len(receptor.list) == 0:
        return
    cuenta = 0
    estado = receptor.list[0]
    # Se cuentan todos los paquetes listos 
    while estado:
        cuenta+=1
        sys.stdout.buffer.write(emisor.list[0].data[2:]) # Escribo en este punto para que no se desordene la escritura de paquetes
        receptor.list.pop(0)
        receptor.list.append(0)
        emisor.list.pop(0)
        if len(receptor.list) > 0:
            estado = receptor.list[0]
        else:
            break
    
    # Se "desliza" la ventana según cuantos paquetes estaban listos
    receptor.anterior += cuenta
    receptor.anterior %= 65536
    emisor.anterior += cuenta
    emisor.anterior %= 65536
    
    receptor.primero += cuenta
    receptor.primero %= 65536
    emisor.primero += cuenta
    emisor.primero %= 65536
    
    receptor.ultimo += cuenta
    receptor.ultimo %= 65536
    emisor.ultimo += cuenta
    emisor.ultimo %= 65536

        


def checkTimeouts(s):
    global timeQueue, timeout, error_envio   
    tiempo_ahora = time.time()
    par = timeQueue.get()
    dif = par[0] - tiempo_ahora
    # Si no hay un tiempo restante del paquete, reviso si llegó
    if dif <= 0:
        estado = par[2].status
        if estado == 0: # si no está listo, lo reenvío seteando lo necesario
            error_envio += 1
            s.send(par[2].data)
            par[2].time = time.time()
            timeQueue.put((par[2].time+timeout, par[2].number,  par[2]))
        else: # Si llegó, actualizo el timeout segpun el rtt
            timeout = (par[2].time_recibido - par[2].time) * 3
    
    else: # Espero el tiempo restante
        mutex_cond.wait(dif)
        estado = par[2].status
        if estado == 0: # si no está listo, lo reenvío seteando lo necesario
            error_envio += 1
            s.send(par[2].data)
            par[2].time = time.time()
            timeQueue.put((par[2].time+timeout, par[2].number,  par[2]))
        else: # Si llegó, actualizo el timeout segpun el rtt
            timeout = (par[2].time_recibido - par[2].time) * 3


if len(sys.argv) != 5:
    print('Use: '+sys.argv[0]+' pack_size, window_size host port')
    sys.exit(1)


s = jsockets.socket_udp_connect(sys.argv[3], sys.argv[4])
if s is None:
    print('could not open socket')
    sys.exit(1)

tamaño = int(sys.argv[1]) - 2

ventana = int(sys.argv[2])

if 1 > ventana or ventana > 32767:
    print('window size have to be between 1 and 32767')
    sys.exit(1)

# ventana de recepcion, tendrá una lista de 0s y 1s, indicando el estado de cada paquete a recibir
recepcion = Window(ventana)


# ventana de emisión, tendrá una lista de paquetes a enviar
arreglo = Window(ventana)

# Cola de prioridad de timeouts, contiene 
# el tiempo límite de llegada de un paquete junto con el mismo paquete
timeQueue = PriorityQueue()

# Inicializo la lista de recepción con 0s
for i in range(ventana):
    recepcion.list.append(0)



# Creo thread que lee desde el socket hacia stdout:
newthread = threading.Thread(target=Rdr, args=(s,tamaño, ))
newthread.start()


timeout = 3

num_total = 0

# En este otro thread leo desde stdin hacia socket:
data=sys.stdin.buffer.read(tamaño)
while(data):

    mutex_cond.acquire()
    # Si hay paquetes en la cola
    while not timeQueue.empty():
        tiempo_ahora = time.time()
        par = timeQueue.get()
        dif = par[0] - tiempo_ahora
        if dif <= 0: # Si el tiempo ya pasó, reviso que sucede
            estado = par[2].status
            if estado == 0: # si no está listo, lo reenvío seteando lo necesario
                error_envio += 1
                s.send(par[2].data)
                par[2].time = time.time()
                timeQueue.put((par[2].time+timeout, par[2].number,  par[2]))
            else: # Si llegó, actualizo el timeout con el rtt
                timeout = (par[2].time_recibido - par[2].time) * 3
        else: # Queda tiempo para que llegue todavía, lo devuelvo a la cola
            timeQueue.put(par)
            break
            

    while(len(arreglo.list) == ventana): # Si la ventana de emisión está llena
        if not timeQueue.empty(): # si hay paquetes en la cola reviso
            checkTimeouts(s)
        else: # sino espero hasta que se libere
            mutex_cond.wait()

    # Creo un objeto paquete inicializandolo con lo necesario
    paquete = enviado.to_bytes(2, 'big')
    data = paquete + data
    s.send(data)
    init_time = time.time()
    package = Package(data, enviado, init_time)
    arreglo.list.append(package)
    # Agrego el tiempo de llegada límite del paquete, junto con el paquete (el segundo elemento de la tupla no es determinante)
    timeQueue.put((timeout+init_time, package.number, package))  
    enviado += 1
    num_total += 1
    enviado = enviado % 65536
    mutex_cond.release()
    data=sys.stdin.buffer.read(tamaño)


mutex_cond.acquire()

# Mientras queden paquetes en la cola, voy constantemente revisando el timeout hasta que lleguen todos los paquetes
while not timeQueue.empty():
    checkTimeouts(s)

# Creo un último paquete para el EOF
package = Package(enviado.to_bytes(2, byteorder='big'), enviado, time.time())
timeQueue.put((timeout+package.time, enviado, package))
s.send(enviado.to_bytes(2, byteorder='big'))
arreglo.list.append(package)
while package.status == 0:
    s.send(enviado.to_bytes(2, byteorder='big'))



terminado = 1
mutex_cond.release()

s.close()


sys.stderr.write(f'Usando: pack: {tamaño+2}, maxwin: {ventana}\n')
# sys.stderr.write(f'Paquetes en total enviados: {num_total}\n')
sys.stderr.write(f'Errores de envío: {error_envio}\n')
sys.stderr.write(f'Errores de recepción: {error_recep}\n')
