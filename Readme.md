Trabajo de fin de grado desarrollado por David Znojek, estudiante de Ingeniería Informática en la Universidad de Alicante, con ayuda del profesor y tutor Francisco Pujol y Tamai Ramirez.

Para poner en funcionamiento la red de entrenamiento distribuido con registro de datos en la Blockchain, es necesario instalar la red de Blockchain Hyperldger Besu con Tessera que viene ya configurada y lista para usar, que es el GoQuorum Quickstart, desarrollada por el grupo GoQuorum. Cabe destacar que el trabajo se ha desarrollado en un entorno WSL de Ubuntu-22.04, por lo que todo está configurado para correr en un entorno de Linux.

Primero necesitamos instalar los prerequisitos del entorno, que son Docker y Node.js:
- Actualización del sistema operativo:
    - sudo apt update
    - sudo apt upgrade -y

- Instalación de dependencias de Docker:
    - sudo apt install -y curl apt-transport-https ca-certificates software-properties-common

- Clave GPG y adición del repositorio de Docker:
    - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    - echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

- Instalación de Docker Engine y Docker Compose:
    - sudo apt update
    - sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

- Permitir al usuario usar Docker (cerrar y volver a abrir la terminal para guardar los cambios después de ejecutar el siguiente comando):
    - sudo usermod -aG docker $USER

- Instalación de node.js:
    - sudo apt install -y nodejs npm

Una vez teniendo todos los elementos instalados, podemos pasar a instalar la red Quickstart. En el mismo directiorio donde tengamos las demás carpetas (Scripts, Smart_Contracts...), ejecutamos el siguiente comando:

- npx quorum-dev-quickstart

Con esto se ejecutará el script de instalación de la red y tendremos que responder a un par de preguntas para llevar a cabo la instalación. Para la pregunta de "Which Ethereum client..." elegimos Hyperledger Besu. Para "Do you wish to enable support for private transactions?", elegimos que sí ("Y"). Para el resto pulsamos la tecla Enter.

Con esto tendremos la red de Blockchain instalada y lista para usar.

Ahora necesitamos instalar las dependencias de los scripts de Python (3.12). Necesitamos instalar las librerías web3 para la interacción con Blockchain y Flower para el entrenamiento distribuido. Para ello ejecutamos el siguiente comando:
- pip install web3 flwr

Ahora sólamente nos falta instalar el servidor de IPFS para el almacenamiento distribuido de los modelos. Para ello, en la terminal ejecutamos la siguiente serie de comandos:
 - wget https://dist.ipfs.tech/kubo/v0.32.1/kubo_v0.32.1_linux-amd64.tar.gz
 - tar -xvzf kubo_v0.32.1_linux-amd64.tar.gz
 - cd kubo
 - sudo ./install.sh
 - ipfs --version  (para comprobar que se ha instalado correctamente)

Con el servidor IPFS instalado, procedemos a inicializarlo, que se hace únicamente la primera vez que se instala, para configurar el repositorio de IPFS. Para ello ejecutamos los siguientes comandos:
 - ipfs init
 - ipfs config --json API.HTTPHeaders.Access-Control-Allow-Origin '["*"]'
 - ipfs config --json API.HTTPHeaders.Access-Control-Allow-Methods '["PUT", "GET", "POST"]'


Con esto tendremos el servidor de IPFS instalado y configurado para su uso en el sistema de entrenamiento distribuido con registro en Blockchain. Con todos los elementos necesarios instalados, ya podemos pasar a ejecutar los scripts para poner en marcha el sistema de entrenamiento distribuido con registro en Blockchain.

Primero ponemos en marcha la red de Blockchain. Para ello nos vamos al directorio donde se ha instalado la red Quickstart y ejecutamos el siguiente comando:

- ./run.sh

(Para parar la ejecución de la red, se puede ejecutar el comando "./stop.sh" en el mismo directorio o el "./restart.sh" para reiniciarla).

Ahora con la red en marcha, ya podemos pasar a ejecutar los scripts que se encuentran en la carpeta "Scripts" para poner en marcha el sistema de entrenamiento distribuido con registro en Blockchain. El proceso es el siguiente:

1. Ejecutamos "contract_address.py" para obtener la dirección del contrato inteligente desplegado en la red de Blockchain. Esta dirección es necesaria para que los miembros de la red puedan interactuar con el contrato inteligente y registrar los datos de entrenamiento. La información del contrato inteligente se guarda en un archivo "FLRegistry_info.json" que se genera al ejecutar el script en "Smart_Contracts/Contract_Data".

2. Ejecutamos "ipfs daemon" para iniciar el servidor de IPFS, que se encargará del almacenamiento distribuido de los modelos entrenados.

3. Ejecutamos "server.py" para iniciar el servidor de entrenamiento distribuido, que se encargará de coordinar el proceso de entrenamiento entre los diferentes clientes y registrar los datos en la Blockchain.

4. Ejecutamos "client.py" en cada uno de los clientes que participarán en el proceso de entrenamiento distribuido, para que puedan conectarse al servidor y participar en el proceso de entrenamiento. Para ello, es necesario ejecutar el siguiente comando:
    - python client.py --member <ID_DEL_CLIENTE>
Donde <ID_DEL_CLIENTE> es un identificador único para cada cliente, que se utiliza para registrar los datos de entrenamiento en la Blockchain. En mi red los únicos clientes que participarán en el entrenamiento serán los clientes con ID 2 y 3.
