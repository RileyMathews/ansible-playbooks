#! /bin/bash
ansible-playbook archinstall.yml -i "$1," --user root --ask-pass -e hostname=$2
