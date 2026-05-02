import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config/flavor.dart';

class ApiService {
  // https://admin.nonbor.uz
  static String get _prodUrl {
    final e = [66,94,94,90,89,16,5,5,75,78,71,67,68,4,68,69,68,72,69,88,4,95,80];
    return String.fromCharCodes(e.map((c) => c ^ 42));
  }

  static String _testServerUrl = '';

  static String get baseUrl => kIsTest ? _testServerUrl : _prodUrl;

  static String _username = '';
  static String _password = '';
  static int? _businessId;
  static String _businessName = '';

  static int? get businessId => _businessId;
  static String get businessName => _businessName;
  static String get username => _username;
  static bool get isConfigured => _username.isNotEmpty && baseUrl.isNotEmpty;

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
    if (kIsTest) _testServerUrl = prefs.getString('test_server_url') ?? '';
  }

  static Future<void> saveConfig({
    String? username,
    String? password,
    int? businessId,
    String? businessName,
    String? testServerUrl,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    if (username != null)      { _username = username; prefs.setString('username', username); }
    if (password != null)      { _password = password; prefs.setString('password', password); }
    if (businessId != null)    { _businessId = businessId; prefs.setInt('business_id', businessId); }
    if (businessName != null)  { _businessName = businessName; prefs.setString('business_name', businessName); }
    if (testServerUrl != null) { _testServerUrl = testServerUrl; prefs.setString('test_server_url', testServerUrl); }
  }

  static Future<void> clearConfig() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    _username = ''; _password = '';
    _businessId = null; _businessName = '';
    _testServerUrl = '';
  }

  // Login → nonbor-admin /api/xprinter-in/agent/auth
  static Future<Map<String, dynamic>> login(String user, String pass) async {
    final url = kIsTest
        ? '$baseUrl/api/v2/agent/auth/'
        : '$baseUrl/api/xprinter-in/agent/auth';
    final resp = await http.post(
      Uri.parse(url),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': user, 'password': pass}),
    ).timeout(const Duration(seconds: 10));
    return jsonDecode(resp.body);
  }

  // Poll → nonbor-admin /api/xprinter-in/agent/poll
  static Future<List<dynamic>> pollJobs() async {
    final url = kIsTest
        ? '$baseUrl/api/v2/print-job/agent/poll/?business_id=$_businessId'
        : '$baseUrl/api/xprinter-in/agent/poll?business_id=$_businessId&username=$_username';
    final resp = await http.get(
      Uri.parse(url),
      headers: _headers,
    ).timeout(const Duration(seconds: 15));
    final data = jsonDecode(resp.body);
    if (data['success'] == true) return data['result'] ?? [];
    return [];
  }

  // Complete → nonbor-admin (result bildirish, ixtiyoriy)
  static Future<bool> completeJob(int jobId, {String status = 'completed', String? error}) async {
    if (kIsTest) {
      final url = '$baseUrl/api/v2/print-job/agent/complete/';
      final resp = await http.post(
        Uri.parse(url),
        headers: _headers,
        body: jsonEncode({'job_id': jobId, 'status': status, 'error': error ?? ''}),
      ).timeout(const Duration(seconds: 10));
      return jsonDecode(resp.body)['success'] == true;
    }
    // Prod: natijani admin ga bildirish
    try {
      await http.post(
        Uri.parse('$baseUrl/api/xprinter-in/print-result'),
        headers: {'Content-Type': 'application/json',
                   'X-API-Key': _xprinterKey},
        body: jsonEncode({
          'order_id': jobId,
          'business_id': _businessId,
          'status': status == 'completed' ? 'printed' : 'failed',
          'error': error ?? '',
        }),
      ).timeout(const Duration(seconds: 5));
    } catch (_) {}
    return true;
  }

  // Health check
  static Future<Map<String, dynamic>> healthCheck() async {
    final url = kIsTest
        ? '$baseUrl/api/v2/health/'
        : '$baseUrl/health';
    final resp = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 5));
    return jsonDecode(resp.body);
  }

  // xprinter-secret-keys (obfuscated)
  static String get _xprinterKey {
    final e = [82,90,88,67,68,94,79,88,7,89,79,73,88,79,94,7,65,79,83,89];
    return String.fromCharCodes(e.map((c) => c ^ 42));
  }
}
