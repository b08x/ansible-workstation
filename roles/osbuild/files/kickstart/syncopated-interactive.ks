# Syncopated installer kickstart, interactive partitioning variant.
#
# Selected by osbuild_kickstart_partitioning: interactive. Same as
# syncopated.ks without the %pre disk selection and its
# %include /tmp/partitions.ks. With no storage commands (ignoredisk, clearpart,
# part, logvol, autopart, ...) Anaconda's Storage module leaves Installation
# Destination incomplete, so the user picks disks and the layout in the GUI.
# Same embedding rules as syncopated.ks: no three consecutive single quotes,
# no Jinja delimiters.
#
# Anaconda asks for three things: Installation Destination, Root Password and
# User Creation.

graphical
firstboot --disable
reboot
network --bootproto=dhcp --device=link --activate --onboot=on
