class Estacion {
  final int id;
  final String nombre;
  final String ubicacion;
  // Cambiamos a double? porque los sensores suelen enviar decimales
  final double? ultimoValor; 

  // Incluimos ultimoValor en el constructor para que se asigne al crear el objeto
  Estacion({
    required this.id, 
    required this.nombre, 
    required this.ubicacion, 
    this.ultimoValor
  });
  
  factory Estacion.fromJson(Map<String, dynamic> json) {
    return Estacion(
      id: json['id'],
      nombre: json['nombre'],
      ubicacion: json['ubicacion'],
      // CLAVE: Mapeamos el valor desde el JSON para que el reto funcione 
      ultimoValor: json['ultimo_valor'] != null 
          ? (json['ultimo_valor'] as num).toDouble() 
          : null,
    );
  }
}