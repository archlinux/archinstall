# Qemu helper

Can be used with the `mkosi` test tooling

After `mkosi -B build` has been executed, run the following:

    python test_tooling/qemu/qemu.py \
        --uki ./test_tooling/mkosi/mkosi.output/image_13.efi \
        --harddrive ~/test.qcow2:15G \
        --harddrive ~/test_large.qcow2:25G

And install using `archinstall`, after the machine has been shutdown, run:

    python test_tooling/qemu/qemu.py \
        --harddrive ~/test.qcow2:15G \
        --harddrive ~/test_large.qcow2:25G

As this will boot EFI mode with just the harddrives to verify the installation.