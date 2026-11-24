#!/bin/sh
set -eu
base=$(CDPATH='' cd -- "$(dirname -- "$0")/../privileged" && pwd)
sudo install -o root -g root -m 0755 "$base/vigil-hotplug" /usr/local/sbin/vigil-hotplug
sudo install -o root -g root -m 0644 "$base/99-vigil-hotplug.rules" /etc/udev/rules.d/99-vigil-hotplug.rules
sudo udevadm control --reload-rules
