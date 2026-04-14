import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import 'dashboard_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _loading = false;
  bool _obscure = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _userCtrl.text = ApiService.username;
  }

  Future<void> _login() async {
    final user = _userCtrl.text.trim();
    final pass = _passCtrl.text.trim();
    if (user.isEmpty || pass.isEmpty) {
      setState(() => _error = "Barcha maydonlarni to'ldiring");
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService.login(user, pass);
      if (data["success"] == true) {
        await ApiService.saveConfig(
          username: user, password: pass,
          businessId: data["business_id"], businessName: data["business_name"] ?? "",
        );
        if (mounted) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(builder: (_) => const DashboardScreen()),
          );
        }
      } else {
        setState(() => _error = data["error"] ?? "Login yoki parol xato");
      }
    } catch (e) {
      setState(() => _error = "Serverga ulanib bo'lmadi");
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
            colors: [AppColors.primary, AppColors.primaryDark],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(children: [
                Container(
                  width: 80, height: 80,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Icon(Icons.print_rounded, size: 44, color: Colors.white),
                ).animate().scale(duration: 400.ms, curve: Curves.easeOut),
                const SizedBox(height: 16),
                const Text("NONBOR", style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: Colors.white, letterSpacing: 3)),
                const Text("Print Agent", style: TextStyle(fontSize: 16, color: Colors.white70)),
                const SizedBox(height: 40),
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white, borderRadius: BorderRadius.circular(24),
                    boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.1), blurRadius: 30, offset: const Offset(0, 10))],
                  ),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    const Text("Tizimga kirish", style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.text)),
                    const SizedBox(height: 4),
                    const Text("Login va parolingizni kiriting", style: TextStyle(fontSize: 14, color: AppColors.textSecondary)),
                    const SizedBox(height: 24),
                    TextField(controller: _userCtrl, decoration: const InputDecoration(labelText: "Login", prefixIcon: Icon(Icons.person_outline))),
                    const SizedBox(height: 14),
                    TextField(controller: _passCtrl, obscureText: _obscure, decoration: InputDecoration(labelText: "Parol", prefixIcon: const Icon(Icons.lock_outline), suffixIcon: IconButton(icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility), onPressed: () => setState(() => _obscure = !_obscure))), onSubmitted: (_) => _login()),
                    const SizedBox(height: 8),
                    if (_error != null) Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: AppColors.error.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(10)), child: Text(_error!, style: const TextStyle(color: AppColors.error, fontSize: 13))),
                    const SizedBox(height: 20),
                    SizedBox(height: 52, child: ElevatedButton(
                      onPressed: _loading ? null : _login,
                      child: _loading
                        ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Row(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.login_rounded), SizedBox(width: 8), Text("Kirish")]),
                    )),
                  ]),
                ).animate().slideY(begin: 0.1, duration: 400.ms, curve: Curves.easeOut).fadeIn(),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
