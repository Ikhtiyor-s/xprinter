import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static String _serverUrl = '';
  static String _username = '';
  static String _password = '';
  static int? _businessId;
  static String _businessName = '';

  static String get serverUrl => _serverUrl;
  static int? get businessId => _businessId;
  static String get businessName => _businessName;
  static String get username => _username;
  static bool get isConfigured => _serverUrl.isNotEmpty;

  static Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    if (_username.isNotEmpty)
      'Authorization': 'Basic ${base64Encode(utf8.encode('$_username:$_password'))}',
  };

  static Future<void> loadConfig() async {
    final prefs = await SharedPreferences.getInstance();
    _serverUrl = prefs.getString('server_url') ?? '';
    _username = prefs.getString('username') ?? '';
    _password = prefs.getString('password') ?? '';
    _businessId = prefs.getInt('business_id');
    _businessName = prefs.getString('business_name') ?? '';
  }

  static Future<void> saveConfig({
    String? serverUrl,
    String? username,
    String? password,
    int? businessId,
    String? businessName,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    if (serverUrl != null) { _serverUrl = serverUrl; prefs.setString('server_url', serverUrl); }
    if (username != null) { _username = username; prefs.setString('username', username); }
    if (password != null) { _password = password; prefs.setString('password', password); }
    if (businessId != null) { _businessId = businessId; prefs.setInt('business_id', businessId); }
    if (businessName != null) { _businessName = businessName; prefs.setString('business_name', businessName); }
  }

  static Future<void> clearConfig() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    _serverUrl = ''; _username = ''; _password = '';
    _businessId = null; _businessName = '';
  }

  static Future<Map<String, dynamic>> login(String server, String user, String pass) async {
    final url = '${server.replaceAll(RegExp(r'/$'), '')}/api/v2/agent/auth/';
    final resp = await http.post(
      Uri.parse(url),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': user, 'password': pass}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(resp.body);
  }

  static Future<List<dynamic>> pollJobs() async {
    final resp = await http.get(
      Uri.parse('$_serverUrl/api/v2/print-job/agent/poll/?business_id=$_businessId'),
      headers: _headers,
    ).timeout(const Duration(seconds: 15));
    final data = jsonDecode(resp.body);
    if (data['success'] == true) return data['jobs'] ?? [];
    return [];
  }

  static Future<bool> completeJob(int jobId, {String action = 'completed', String? error}) async {
    final body = {'jobs': [{'job_id': jobId, 'action': action, if (error != null) 'error': error}]};
    final resp = await http.post(
      Uri.parse('$_serverUrl/api/v2/print-job/agent/complete/'),
      headers: _headers,
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 10));
    final data = jsonDecode(resp.body);
    return data['success'] == true;
  }

  static Future<Map<String, dynamic>> healthCheck() async {
    final resp = await http.get(
      Uri.parse('$_serverUrl/api/v2/health/'),
    ).timeout(const Duration(seconds: 5));
    return jsonDecode(resp.body);
  }

  static Future<List<dynamic>> fetchMenu() async {
    final resp = await http.get(
      Uri.parse('$_serverUrl/api/v2/agent/menu/$_businessId/?username=$_username&password=$_password'),
      headers: _headers,
    ).timeout(const Duration(seconds: 30));
    final data = jsonDecode(resp.body);
    if (data['success'] == true) return data['products'] ?? [];
    return [];
  }
}
