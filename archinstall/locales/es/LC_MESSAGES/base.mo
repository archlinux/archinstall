��    m      �  �   �      @	  L   A	  Z   �	  i   �	     S
     Y
     n
     �
  $   �
  <   �
  "   	     ,     @  ;   W  #   �  #   �     �     �  .   	     8  3   O     �     �  '   �     �  1   �  3   &  "   Z     }  E   �  @   �  3     :   K  L   �  B   �  :     @   Q  ,   �  0   �  w   �  v   h  i   �  �   I  e   �     =     E  9   d  $   �  4   �  1   �  v   *     �     �     �     �               ,     >     Q     c     r     �     �     �  )   �  3   �  &   *  3   Q  )   �     �     �  J   �  :   $  D   _  6   �  H   �     $  &   B     i     �     �  )   �     �     �     �          *  p   C     �  Q   �       6   !  H   X  G   �  C   �  Z   -  #   �  M   �  �   �  ]   �  +     2   F  .   y  .   �  /   �  1     1   9  D   k  �   �  r   j  `   �  n   >     �     �     �  "   �  $      N   7   ,   �      �      �   G   �   #   2!     V!  &   s!     �!  5   �!     �!  7   �!  '   5"     ]"  '   u"     �"  C   �"  E   �"  -   @#     n#  _   �#  P   �#  J   <$  :   �$  S   �$  O   %  U   f%  U   �%  :   &  4   M&  �   �&  �   '  k   �'  �   �'  a   �(     )  !   
)  F   ,)  /   s)  E   �)  B   �)  s   ,*  &   �*  (   �*  #   �*  '   +     <+     X+  "   l+  )   �+     �+     �+  '   �+  !   ,     6,      Q,  .   r,  6   �,  /   �,  9   -  )   B-     l-     �-  R   �-  J   �-  [   B.  G   �.  V   �.  7   =/  =   u/  $   �/  !   �/  ,   �/  3   '0     [0     z0  %   �0      �0      �0  {   �0     t1  U   �1  	   �1  =   �1  R   )2  Z   |2  H   �2  o    3     �3  a   �3  �   4  |   �4  6   V5  B   �5  5   �5  3   6  5   :6  5   p6  D   �6  S   �6     0   <       	   F             #             N   L         *          P   A       K   7   X   V   Z         4   R       /            Y   .   e   =      2               1   ?       !   W   f   "       ^       k                       [       %   b   I   C   
              6   a       +   m          h      g   Q       (       $                  ;   ]   ,   9   @   S   O          T       i   \             _   B   c   l             d          :   G   >      j   5       8   U           E   &   J   3   H      )   M      '                  D   `          -            

Select a graphics driver or leave blank to install all open-source drivers     Please submit this issue (and file) to https://github.com/archlinux/archinstall/issues  * Partition mount-points are relative to inside the installation, the boot would be /boot as an example. Abort Adding partition.... Additional packages to install All open-source (default) And one more time for verification:  Any additional users to install (leave blank for no users):  Assign mount-point for a partition Choose a bootloader Choose an audio server Choose which kernels to use or leave blank for default "{}" Choose which locale encoding to use Choose which locale language to use Clear/Delete all partitions Configure network Copy ISO network configuration to installation Create a new partition Create a required super-user with sudo privileges:  Current partition layout Delete a partition Desired hostname for the installation:  Do you really want to abort? Enter a desired filesystem type for the partition Enter a desired filesystem type for the partition:  Enter a encryption password for {} Enter a password:  Enter a username to create an additional user (leave blank to skip):  Enter disk encryption password (leave blank for no encryption):  Enter root password (leave blank to disable root):  Enter the IP and subnet for {} (example: 192.168.0.5/24):  Enter the end sector of the partition (percentage or block number, ex: {}):  Enter the start sector (percentage or block number, default: {}):  Enter your DNS servers (space separated, blank for none):  Enter your gateway (router) IP address or leave blank for none:  Error: Could not decode "{}" result as JSON: Error: Listing profiles on URL "{}" resulted in: For the best compatibility with your AMD hardware, you may want to use either the all open-source or AMD / ATI options. For the best compatibility with your Intel hardware, you may want to use either the all open-source or Intel options.
 For the best compatibility with your Nvidia hardware, you may want to use the Nvidia proprietary driver.
 Hardware time and other post-configuration steps might be required in order for NTP to work.
For more information, please check the Arch wiki If you desire a web browser, such as firefox or chromium, you may specify it in the following prompt. Install Install ({} config(s) missing) Mark/Unmark a partition as bootable (automatic for /boot) Mark/Unmark a partition as encrypted Mark/Unmark a partition to be formatted (wipes data) Not configured, unavailable unless setup manually Only packages such as base, base-devel, linux, linux-firmware, efibootmgr and optional profile packages are installed. Password for user "{}":  Re-using partition instance: {} Select Archinstall language Select Keyboard layout Select a timezone Select audio Select bootloader Select disk layout Select harddrives Select kernels Select keyboard layout Select locale encoding Select locale language Select mirror region Select one network interface to configure Select one of the regions to download packages from Select one of the values shown below:  Select one or more hard drives to use and configure Select one or more of the options below:  Select timezone Select what to do with
{} Select what to do with each individual drive (followed by partition usage) Select what you wish to do with the selected block devices Select where to mount partition (leave blank to remove mountpoint):  Select which filesystem your main partition should use Select which mode to configure for "{}" or skip to use default mode "{}" Set automatic time sync (NTP) Set desired filesystem for a partition Set encryption password Set root password Set/Modify the below options Should this user be a superuser (sudoer)? Specify hostname Specify profile Specify superuser account Specify user account Suggest partition layout This is a list of pre-programmed profiles, they might make it easier to install things like desktop environments Use ESC to skip

 Use NetworkManager (necessary to configure internet graphically in GNOME and KDE) Use swap Username for required superuser with sudo privileges:  Verifying that additional packages exist (this might take a few seconds) Wipe all selected drives and use a best-effort default partition layout Would you like to use GRUB as a bootloader instead of systemd-boot? Would you like to use automatic time synchronization (NTP) with the default time servers?
 Would you like to use swap on zram? Write additional packages to install (space separated, leave blank to skip):  You decided to skip harddrive selection
and will use whatever drive-setup is mounted at {} (experimental)
WARNING: Archinstall won't check the suitability of this setup
Do you wish to continue? You need to enter a valid fs-type in order to continue. See `man parted` for valid fs-type's. [!] A log file has been created here: {} {} {}

Select by index which partition to mount where {}

Select by index which partitions to delete {}

Select which partition to mark as bootable {}

Select which partition to mark as encrypted {}

Select which partition to mask for formatting {}

Select which partition to set a filesystem on {} contains queued partitions, this will remove those, are you sure? Project-Id-Version: 
PO-Revision-Date: 
Language-Team: 
Language: es
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit
X-Generator: Poedit 3.0.1
 

Selecciona un controlador de gráficos o deja en blanco para instalar todos los controladores de código abierto     Por favor envíe este problema (y archivo) a https://github.com/archlinux/archinstall/issues  * Los puntos de montaje de partición son relativos a la instalación, el arranque sería /boot como ejemplo. Cancelar Añadiendo partición... Paquetes adicionales a instalar Todo código abierto (por defecto) Una última vez para verificación:  Algún usuario adicional a instalar (deje en blanco para no agregar ninguno):  Asignar punto de montaje para una partición Elige un gestor de arranque Elige un servidor de audio Elige qué kernels usar o deja en blanco para usar los por defecto "{}" Elige qué codificación local usar Elige qué idioma local usar Limpiar/Eliminar todas las particiones Configurar la red Copiar la configuración de red ISO a la instalación Crear una nueva partición Crear un super-usuario requerido con privilegios sudo:  Distribución actual de las particiones Eliminar una partición Hostname deseado para la instalación:  Realmente desea abortar? Escriba el tipo de sistema de archivos que desea para la partición Escriba el tipo de sistema de archivos que desea para la partición:  Introduzca una contraseña de cifrado para {} Introduzca una contraseña:  Introduzca un nombre de usuario para crear un usuario adicional (dejar en blanco para saltar):  Introduzca la contraseña de cifrado de disco (dejar en blanco para no cifrar):  Introduzca la contraseña de root (dejar en blanco para desactivar root):  Escriba la IP y subred para {} (ejemplo: 192.168.0.5/24):  Escriba el sector final de la partición (porcentaje o número de bloque, ej: {}):  Escriba el sector de inicio (porcentaje o número de bloque, por defecto: {}):  Escriba los servidores DNS (separados por espacios, en blanco para no usar ninguno):  Escriba la IP de su puerta de enlace (router) o deje en blanco para no usar ninguna:  Error: No se pudo decodificar el resultado "{}" como JSON: Error: Enlistar perfiles en la URL "{}" resultó en: Para la mejor compatibilidad con tu hardware AMD, puedes querer usar tanto la opción de todo código abierto como la opción AMD / ATI. Para la mejor compatibilidad con tu hardware Intel, puedes querer usar tanto la opción de todo código abierto como la opción Intel.
 Para la mejor compatibilidad con tu hardware Nvidia, puedes querer usar el controlador propietario Nvidia.
 La hora del hardware y otros pasos post-configuración pueden ser necesarios para que NTP funcione. Para más información, por favor, consulte la wiki de Arch Si desea un navegador web, como firefox o chromium, puede especificarlo en el siguiente diálogo. Instalar Instalar ({} ajuste(s) faltantes) Marcar/Desmarcar una partición como bootable (automática para /boot) Marcar/Desmarcar una partición como encriptada Marcar/Desmarcar una partición para ser formateada (borra los datos) No configurado, no disponible a menos que se configure manualmente Solo paquetes como base, base-devel, linux, linux-firmware, efibootmgr y paquetes opcionales de perfil se instalan. Contraseña para el usuario “{}”:  Reutilizando instancia de partición: {} Selecciona el idioma de Archinstall Selecciona la distribución del teclado Selecciona una zona horaria Selecciona el audio Selecciona el cargador de arranque Selecciona la distribución de los discos Selecciona los discos duros Selecciona los kernels Selecciona la distribución del teclado Selecciona la codificación local Selecciona el idioma local Selecciona la región del mirror Selecciona una interfaz de red para configurar Selecciona una de las regiones para descargar paquetes Selecciona uno de los valores mostrados abajo:  Selecciona uno o más discos duros para usar y configurar Selecciona una o más opciones de abajo:  Selecciona la zona horaria Selecciona qué hacer con
{} Selecciona qué hacer con cada disco individual (seguido por el uso de partición) Selecciona qué quieres hacer con los dispositivos de bloque seleccionados Selecciona dónde montar la partición (deja en blanco para eliminar el punto de montaje):  Selecciona el sistema de archivos que su partición principal debe usar Selecciona el modo para configurar "{}" u omitir para usar el modo "{}" predeterminado Establecer la sincronización automática de hora (NTP) Establecer el sistema de archivos deseado para una partición Establecer la contraseña de cifrado Establecer la contraseña de root Establecer/Modificar las opciones siguientes Debería este usuario ser un superusuario (sudoer)? Especificar el nombre del host Especificar el perfil Especificar la cuenta de superusuario Especificar la cuenta de usuario Sugerir el diseño de partición Esta es una lista de perfiles pre-programados, pueden facilitar la instalación de aplicaciones como entornos de escritorio Usar ESC para saltar

 Usar NetworkManager (necesario para configurar internet gráficamente en GNOME y KDE) Usar swap Nombre de usuario para el superusuario con privilegios sudo:  Verificando que los paquetes adicionales existen (esto puede tardar unos segundos) Limpiar todos los discos seleccionados y usar una distribución de particiones por defecto Te gustaría usar GRUB como gestor de arranque en lugar de systemd-boot? Te gustaría utilizar la sincronización automática de hora (NTP) con los servidores de hora predeterminados?
 Te gustaría usar swap en zram? Escriba paquetes adicionales para instalar (separados por espacios, deja en blanco para omitir):  Has decidido saltar la selección de discos duros
y usar la configuración montada en {} (experimental)
ADVERTENCIA: Archinstall no verificará la idoneidad de esta configuración
¿Desea continuar? Necesitas ingresar un tip de filesystem valido para continuar. Vea `man parted` para tipos de sistemas de archivos válidos. [!] Un archivo de registro ha sido creado aquí: {} {} {}

Selecciona por índice la ubicación de la partición a montar {}

Selecciona por índice las particiones a eliminar {}

Selecciona la partición a marcar como bootable {}

Selecciona la partición a marcar como encriptada {}

Selecciona la partición a ocultar para formatear {}

Selecciona la partición a configurar con un sistema de archivos {} contiene particiones en cola, esto eliminará esas particiones, ¿estás seguro? 