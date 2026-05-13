import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/estacion.dart';
import 'auth_service.dart';

class ApiService {
  // ¡Aquí está tu baseUrl! Al estar aquí arriba, todas las funciones de abajo pueden usarla.
  final String baseUrl = "http://127.0.0.1:8000"; 

  // --- GET: Leer estaciones con Robustez (Lab 7.1) ---
  Future<List<Estacion>> fetchEstaciones() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/estaciones/'))
          .timeout(const Duration(seconds: 5)); 

      if (response.statusCode == 200) {
        List jsonResponse = json.decode(response.body);
        return jsonResponse.map((data) => Estacion.fromJson(data)).toList();
      } else {
        throw Exception('Error del servidor: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('No se pudo conectar con SMAT. ¿Está el servidor activo?');
    }
  }

  // --- POST: Crear estación (Lab 6.1) ---
  Future<bool> crearEstacion(String nombre, String ubicacion) async {
    final token = await AuthService().getToken();
    final response = await http.post(
      Uri.parse('$baseUrl/estaciones/'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token'
      },
      body: jsonEncode({'nombre': nombre, 'ubicacion': ubicacion}),
    );
    return response.statusCode == 200;
  }

  // --- DELETE: Eliminar estación (Lab 6.2) ---
  Future<bool> eliminarEstacion(int id) async {
    final token = await AuthService().getToken();
    final response = await http.delete(
      Uri.parse('$baseUrl/estaciones/$id'),
      headers: {'Authorization': 'Bearer $token'},
    );
    return response.statusCode == 200;
  }

  // --- PUT: Editar estación (Lab 6.2) ---
  Future<bool> editarEstacion(int id, String nombre, String ubicacion) async {
    final token = await AuthService().getToken();
    final response = await http.put(
      Uri.parse('$baseUrl/estaciones/$id'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token'
      },
      body: jsonEncode({'nombre': nombre, 'ubicacion': ubicacion}),
    );
    return response.statusCode == 200;
  }
}