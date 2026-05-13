import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/estacion.dart';
import 'auth_service.dart';

class ApiService {
// 10.0.2.2 es el alias del localhost de la PC para emuladores Android
  final String baseUrl = "http://localhost:8000";

  Future<List<Estacion>> fetchEstaciones() async {
    final response = await http.get(Uri.parse('$baseUrl/estaciones/'));

    if (response.statusCode == 200) {
      List jsonResponse = json.decode(response.body);
      return jsonResponse.map((data) => Estacion.fromJson(data)).toList();
    
    } else {
      throw Exception('Error al conectar con el servidor SMAT');
    }
  }
  Future<bool> crearEstacion(String nombre, String ubicacion) async {
  final token = await AuthService().getToken();

  final response = await http.post(
    Uri.parse('$baseUrl/estaciones/'),
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    },
    body: jsonEncode({
      'nombre': nombre,
      'ubicacion': ubicacion,
    }),
  );

  return response.statusCode == 201 || response.statusCode == 200;
}
}
