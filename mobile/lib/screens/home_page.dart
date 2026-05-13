import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../models/estacion.dart';
import 'login_screen.dart';
import 'add_estacion.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late Future<List<Estacion>> futureEstaciones;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _refreshData(); // Carga inicial de datos [cite: 287]
  }

  // Lab 7.1: Lógica para actualizar los datos (Pull-to-refresh) [cite: 563, 725]
  Future<void> _refreshData() async {
    setState(() {
      futureEstaciones = _apiService.fetchEstaciones();
    });
  }

  // Lab UX: Diálogo modal para editar una estación sin cambiar de pantalla [cite: 682-719]
  void _mostrarDialogoEdicion(Estacion estacion) {
    final nombreCtrl = TextEditingController(text: estacion.nombre);
    final ubicacionCtrl = TextEditingController(text: estacion.ubicacion);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("Editar Estación"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: nombreCtrl, decoration: const InputDecoration(labelText: "Nombre")),
            TextField(controller: ubicacionCtrl, decoration: const InputDecoration(labelText: "Ubicación")),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Cancelar"),
          ),
          ElevatedButton(
            onPressed: () async {
              bool ok = await _apiService.editarEstacion(estacion.id, nombreCtrl.text, ubicacionCtrl.text);
              if (ok && mounted) {
                Navigator.pop(context);
                _refreshData(); // Refresca la lista tras editar [cite: 714]
              }
            },
            child: const Text("Guardar"),
          )
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Estaciones SMAT'),
        actions: [
          // Lab 6.1/6.3: Botón de Logout para limpiar el token y salir [cite: 164, 456-475]
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await AuthService().logout();
              if (!mounted) return;
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (context) => const LoginScreen()),
                (route) => false, // Borra el historial de navegación [cite: 473]
              );
            },
          ),
        ],
      ),
      // Lab 7.1: Implementación de Pull-to-Refresh 
      body: RefreshIndicator(
        onRefresh: _refreshData,
        child: FutureBuilder<List<Estacion>>(
          future: futureEstaciones,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator()); // Feedback visual de carga [cite: 297, 598]
            } else if (snapshot.hasError) {
              // Lab 7.1: Gestión de resiliencia ante errores de red [cite: 544, 595]
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: Text(
                    '❌ ${snapshot.error}',
                    textAlign: TextAlign.center,
                  ),
                ),
              );
            } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
              return const Center(child: Text('No hay estaciones registradas.'));
            } else {
              return ListView.builder(
                itemCount: snapshot.data!.length,
                itemBuilder: (context, index) {
                  final estacion = snapshot.data![index];

                  // Reto UX: Lógica de colores (Alerta Temprana) [cite: 722-724]
                  // Rojo si > 50 (Peligro), Verde si < 50 (Normal).
                  Color colorIcono = (estacion.ultimoValor ?? 0) > 50 ? Colors.red : Colors.green;

                  // Lab UX: Gesto de deslizar para eliminar (Swipe-to-dismiss) [cite: 646-677]
                  return Dismissible(
                    key: Key(estacion.id.toString()),
                    direction: DismissDirection.endToStart,
                    background: Container(
                      color: Colors.red,
                      alignment: Alignment.centerRight,
                      padding: const EdgeInsets.only(right: 20),
                      child: const Icon(Icons.delete, color: Colors.white), // Indicador visual de borrado [cite: 651-656]
                    ),
                    confirmDismiss: (direction) async {
                      // Confirmación opcional: podrías añadir un diálogo aquí
                      return true;
                    },
                    onDismissed: (direction) async {
                      bool ok = await _apiService.eliminarEstacion(estacion.id);
                      if (ok && mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text("${estacion.nombre} eliminada")), // Notificación de éxito [cite: 659]
                        );
                      }
                    },
                    child: ListTile(
                      leading: Icon(Icons.satellite_alt, color: colorIcono), // Icono con color dinámico [cite: 723]
                      title: Text(estacion.nombre),
                      subtitle: Text(estacion.ubicacion),
                      onTap: () => _mostrarDialogoEdicion(estacion), // Click para editar [cite: 675]
                    ),
                  );
                },
              );
            }
          },
        ),
      ),
      // Botón flotante para navegar a la pantalla de creación [cite: 89, 326]
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final result = await Navigator.push(
            context,
            MaterialPageRoute(builder: (context) =>  AddEstacionScreen()),
          );
          if (result == true) {
            _refreshData(); // Refresca si se creó una estación nueva [cite: 328]
          }
        },
        child: const Icon(Icons.add),
      ),
    );
  }
}