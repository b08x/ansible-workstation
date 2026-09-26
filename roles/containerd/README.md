# containerd

# todo

So we should probably... All right, so... Oh, ensure that if NVIDIA or CUDA is detected on the host to install NVIDIA container toolkit toolkit and the necessary prerequisites for ensuring either Podman or Docker can utilize the GPU.


So it seems like going forward on RHEL hosts, Podman will be the default container engine with Docker Compose, Docker compatibility layer. The EL10 Docker Community Edition repositories only contain the BuildX and Compose plugins. The runtime binary either hasn't been cleared yet or that's being phased out.
