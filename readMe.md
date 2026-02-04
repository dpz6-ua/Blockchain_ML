Trabajo de fin de grado desarrollado por David Znojek, estudiante de Ingeniería Informática en la Universidad de Alicante, con ayuda del tutor Francisco Pujol.

Para poner en funcionamiento la red de entrenamiento distribuido con registro de datos en la Blockchain, es necesario instalar la red de Blockchain Hyperldger Besu con Tessera que viene ya configurada y lista para usar, que es el GoQuorum Quickstart, desarrollada por el grupo GoQuorum. Cabe destacar que el trabajo se ha desarrollado en un entorno WSL de Ubuntu-22.04, por lo que todo está configurado para correr en un entorno de Linux.

Primero necesitamos instalar los prerequisitos del entorno, que son Docker y Node.js:
- Actualización del sistema operativo:
    sudo apt update
    sudo apt upgrade -y

- Instalación de dependencias de Docker:
    sudo apt install -y curl apt-transport-https ca-certificates software-properties-common

- Clave GPG y adición del repositorio de Docker:
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

- Instalación de Docker Engine y Docker Compose:
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

- Permitir al usuario usar Docker (cerrar y volver a abrir la terminal para guardar los cambios después de ejecutar el siguiente comando):
    sudo usermod -aG docker $USER

- Instalación de node.js:
    sudo apt install -y nodejs npm

Una vez teniendo todos los elementos instalados, podemos pasar a instalar la red Quickstart. En el mismo directiorio donde tengamos las demás carpetas (Scripts, Smart_Contracts...), ejecutamos el siguiente comando:

- npx quorum-dev-quickstart

Con esto se ejecutará el script de instalación de la red y tendremos que responder a un par de preguntas para llevar a cabo la instalación. Para la pregunta de "Which Ethereum client..." elegimos Hyperledger Besu. Para "Do you wish to enable support for private transactions?", elegimos que sí ("Y"). Para el resto pulsamos la tecla Enter.

Con esto tendremos la red de Blockchain instalada y lista para usar.

Ahora necesitamos instalar las dependencias de los scripts de Python (3.12). Necesitamos instalar las librerías web3 para la interacción con Blockchain y Flower para el entrenamiento distribuido. Para ello ejecutamos el siguiente comando:
- pip install web3 flwr

Ahora sólamente nos falta instalar un servidor de IPFS para el almacenamiento distribuido de los modelos. Para ello, en la terminal ejecutamos el siguiente comando:

Teniendo la red instalada, ya podemos pasar a ejecutar los scripts que se encuentran en la carpeta "Scripts" para poner en marcha el sistema de entrenamiento distribuido con registro en Blockchain. El proceso es el siguiente: