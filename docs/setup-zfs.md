# Setting up ZFS

## Set contrib repository
make sure sources list file includes contrib repository

add contrib to the end of the line
```bash
deb http://deb.debian.org/debian buster main contrib
```

## Install zfs
```bash
sudo apt update
sudo apt install zfsutils-linux zfs-dkms
```

## Load kernel module
```bash
sudo modprobe zfs
```

## Create mirror
```bash
sudo zpool create mypool mirror /dev/sdb /dev/sdc mirror /dev/sdd /dev/sde
```

## setup settings
```
sudo zfs set compression=lz4 mypool
sudo zfs set mountpoint=/data mypool
```

## Enable systemd services
```bash
sudo systemctl enable zfs-import-cache
sudo systemctl enable zfs-mount
sudo systemctl enable zfs-import.target
sudo systemctl enable zfs.target
```

Then reboot

## Check status
```bash
sudo zpool status
```

## Create dataset
```bash
sudo zfs create mypool/data
```

# NFS
## Install kernel server
```bash
sudo apt install nfs-kernel-server
sudo systemctl enable --now nfs-server
sudo zfs set sharenfs="rw=@10.0.0.1/24" mypool/dataset
```
