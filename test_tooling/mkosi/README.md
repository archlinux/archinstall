# To build

    mkosi build -B

# To run

    mkosi qemu \
        --drive=archinstall_small:25G \
        -- \
        -device nvme,serial=archinstall_small,drive=archinstall_small

*note: in order to boot the installation, we need to disable UKI being added to -kernel. I don't know of a way to do this yet, unless we tinker with mkosi/qemu.py - https://github.com/Torxed/mkosi/commit/6f3c20802bd73f88b672cc96ef0db1e542084316 - in which case we could do: `mkosi qemu --drive=archinstall_small:25G -- -device nvme,serial=archinstall_small,drive=archinstall_small,bootindex=0 -kernel none` but it still won't boot properly.*