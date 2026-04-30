import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static String get _baseUrl {
    final e = [66,94,94,90,89,16,5,5,90,88,67,68,94,79,88,4,68,69,68,72,69,88,4,95,80];
    return String.fromCharCodes(e.map((c) => c ^ 42));
  }

  static String _username = '';
  static String _password = '';
  static int? _businessId;
  static String _businessName = '';

  static int? get businessId => _businessId;
  static String get businessName => _businessName;
  static String get username => _username;
  static bool get isConfigured => _username.isNotEmpty;

  static Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    if (_username.isNotEmpty)
      'Authorization': 'Agent $_username:$_password',
  };

  static Future<void> loadConfig() async {
    final prefs = await SharedPreferences.getInstance();
    _username = prefs.getString('username') ?? '';
    _password = prefs.getString('password') ?? '';
    _businessId = prefs.getInt('business_id');
    _businessName = prefs.getString('business_name') ?? '';
  }

  static Future<void> saveConfig({
    String? username,
    String? password,
    int? businessId,
    String? businessName,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    if (username != null) { _username = username; prefs.setString('username', username); }
    if (password != null) { _password = password; prefs.setString('password', password); }
    if (businessId != null) { _businessId = businessId; prefs.setInt('business_id', businessId); }
    if (businessName != null) { _businessName = businessName; prefs.setString('business_name', businessName); }
  }

  static Future<void> clearConfig() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    _username = ''; _password = '';
    _businessId = null; _businessName = '';
  }

  static Future<Map<String, dynamic>> login(String user, String pass) async {
    final url = '$_baseUrl/api/v2/agent/auth/';
    final resp = await http.post(
      Uri.parse(url),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': user, 'password': pass}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(resp.body);
  }

  static Future<List<dynamic>> pollJobs() async {
    final resp = await http.get(
      Uri.parse('$_baseUrl/api/v2/print-job/agent/poll/?business_id=$_businessId'),
      headers: _headers,
    ).timeout(const Duration(seconds: 15));
    final data = jsonDecode(resp.body);
    if (data['success'] == true) return data['result'] ?? [];
    return [];
  }

  static Future<bool> completeJob(int jobId, {String status = 'completed', String? error}) async {
    final body = {'job_id': jobId, 'status': status, 'error': error ?? ''};
    final resp = await http.post(
      Uri.parse('$_baseUrl/api/v2/print-job/agent/complete/'),
      headers: _headers,
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 10));
    final data = jsonDecode(resp.body);
    return data['success'] == true;
  }

  static Future<Map<String, dynamic>> healthCheck() async {
    final resp = await http.get(
      Uri.parse('$_baseUrl/api/v2/health/'),
    ).timeout(const Duration(seconds: 5));
    return jsonDecode(resp.body);
  }
}
