#!/bin/sh
set -eu

script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_directory/../lib/vigil-terminal.sh"

vigil_banner 'Vigil · Installation de la règle udev / Installing the udev rule'
printf '%s\n' 'FR — sudo installe l’outil et la règle, puis recharge udev pour les prochains branchements.' \
    'EN — sudo installs the helper and rule, then reloads udev for future connections.' ''
base=$(CDPATH='' cd -- "$(dirname -- "$0")/../privileged" && pwd)
sudo install -o root -g root -m 0755 "$base/vigil-hotplug" /usr/local/sbin/vigil-hotplug
sudo install -o root -g root -m 0644 "$base/99-vigil-hotplug.rules" /etc/udev/rules.d/99-vigil-hotplug.rules
sudo udevadm control --reload-rules
