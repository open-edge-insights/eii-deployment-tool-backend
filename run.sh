#!/bin/bash

# Copyright (c) 2021 Intel Corporation.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

function setupHost() {
    # setup secure ssh
    if ! [ -f ./id_rsa.pub ];then
        echo "Generating ssh key..."
        ssh-keygen -f id_rsa
    fi
    ssh-copy-id -i id_rsa.pub $USER@localhost
    # add user to sudoers
    sudo grep 'NOPASSWD' /etc/sudoers.d/$USER > /dev/null 2>&1
    if [ "$?" -ne 0 ];then
        echo "Adding user $USER to sudoers..." 
        echo "$USER ALL=(ALL:ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/$USER
    fi
}


function sourceEnv() {
    set -a
    source ../build/.env
    set +a
}

function create_docker_network() {
    echo "Checking eii docker network.."
    docker_networks=$(docker network ls --filter name=eii| awk '{print $2}')
    docker_net_list=(`echo ${docker_networks}`);
    network_present=false
    for dn in "${docker_net_list[@]}"
    do
        if [[ "$dn" = "eii" ]];then
            network_present=true
            break
        fi
    done
    if [[ "$network_present" = false ]]; then
        echo "Creating eii docker bridge network as it is not present.."
        docker network create eii
    fi
}

function check_certs() {
    if [ ! -d ./certificates ]; then
        sudo chmod auo+x ./gen_certs.sh
        sudo ./gen_certs.sh
        sudo chown -R $USER:$USER ./certificates
    fi
}

sourceEnv

if [ "$1" ==  "--build" -o "$1" == "-b" ]; then
    create_docker_network && \
    check_certs && \
    docker-compose down && \
    setupHost && \
    docker-compose build $2 && \
    docker-compose up -d
elif [ "$1" ==  "--restart" -o "$1" == "-r" ]; then
    docker-compose down && \
    docker-compose up -d
elif [ "$1" ==  "--down" -o "$1" == "-d" ]; then
    docker-compose down
elif [ "$1" ==  "--up" -o "$1" == "-u" ]; then
    docker-compose up -d
elif [ "$1" != "" ]; then
    echo "Error: unexpected param: $1"
    exit 
else
    docker-compose up -d
fi
