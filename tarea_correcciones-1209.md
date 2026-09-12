#Consideración: 
Visibilidad de los planos. Los planos de rescate de los templates, pueden accederse desde la aplicación haciendo click en el botón ver plano de la pantalla de gestión de planos, pero estando logueado con usuarios de aplicación (administrador) no un usuario cliente. 
El pdf no debe poder verse directamente desde el cloud storage (generá un archivo storage_config.md con los pasos para configurar correctamente el azure cloud storage) 
Las hojas de rescate deben verse pasando por la aplicación, que debe validar si está activo el qr, si están los datos de combustible, etc... 


-----------
##TAREA 1 - end point /admin/activos/1/planes
- aparece el dato ubicación pero no existe más la ubicación. quitar ubicación y poner Dominio. Poner ambos datos en el mismo renglón.

- cuando clikeas el ícono de "ver plano" falla. 

------------
##TAREA 2 -/hoja-rescate/1
en el apartado "hoja de rescate oficial del fabricante" da el error: 
ResourceNotFoundThe specified resource does not exist. RequestId:379f3cc1-001e-0086-0602-436f59000000 Time:2026-09-12T22:03:20.9470873Z

----------
##TAREA 3 -/hoja-rescate/1
Quitar los datos de titular de esta página. 
los botones "abrir pantalla completa" y "Descargar" no funcionan. Deberían abrir y descargar directamente el pdf o jgp de la hoja de rescate.
imprimir debería el marco web y además el contenido de todas las paginas del pdf o de la foto de la hoja de rescate. 

----------
##TAREA 4 - admin/vehicle_templates
Cuando le das a "ver documento" va directamente al documento en cloud storage y falla. Debe pasar por aplicación, para que sea esta la que valide el usuario.

----------
##TAREA 5 - /admin/qr/gestion
Al generar el qr (dar click al botón generar QR) debe también descargar automáticamente el archivo .zip con los png de los qrs generados.

----------
##TAREA 6 - cliente/activos/1/editar
debe permitir cambiar el plano del vehículo asociado.
