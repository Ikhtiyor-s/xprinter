import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import '../config/flavor.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import 'dashboard_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _serverCtrl = TextEditingController();
  final _userCtrl   = TextEditingController();
  final _passCtrl   = TextEditingController();
  bool _loading = false;
  bool _obscure = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _userCtrl.text = ApiService.username;
    if (kIsTest) _serverCtrl.text = ApiService.baseUrl;
  }

  @override
  void dispose() {
    _serverCtrl.dispose();
    _userCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final user   = _userCtrl.text.trim();
    final pass   = _passCtrl.text.trim();
    final server = kIsTest ? _serverCtrl.text.trim() : null;

    if (user.isEmpty || pass.isEmpty || (kIsTest && (server?.isEmpty ?? true))) {
      setState(() => _error = "Barcha maydonlarni to'ldiring");
      return;
    }
    if (kIsTest) await ApiService.saveConfig(testServerUrl: server);

    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService.login(user, pass);
      if (data["success"] == true) {
        await ApiService.saveConfig(
          username: user, password: pass,
          businessId: data["business_id"],
          businessName: data["business_name"] ?? "",
        );
        if (mounted) {
          Navigator.of(context).pushReplacement(
            CupertinoPageRoute(builder: (_) => const DashboardScreen()),
          );
        }
      } else {
        setState(() => _error = data["error"] ?? "Login yoki parol xato");
      }
    } catch (_) {
      setState(() => _error = "Serverga ulanib bo'lmadi");
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: IosColors.systemGroupedBg,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            children: [
              const SizedBox(height: 60),

              // Logo + Title
              Column(children: [
                Container(
                  width: 80, height: 80,
                  decoration: BoxDecoration(
                    color: IosColors.blue,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: IosColors.blue.withValues(alpha: 0.35),
                        blurRadius: 20,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: const Icon(CupertinoIcons.printer, size: 40, color: Colors.white),
                ),
                const SizedBox(height: 16),
                const Text("Nonbor",
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700,
                      letterSpacing: -0.5, color: IosColors.label)),
                const SizedBox(height: 4),
                Text(
                  kIsTest ? "Print Agent · TEST" : "Print Agent",
                  style: const TextStyle(fontSize: 15, color: IosColors.secondaryLabel),
                ),
              ]),

              const SizedBox(height: 40),

              // Form card
              Container(
                decoration: BoxDecoration(
                  color: IosColors.card,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(
                  children: [
                    if (kIsTest) ...[
                      _Field(
                        controller: _serverCtrl,
                        label: "Server URL",
                        hint: "http://localhost  yoki  http://192.168.X.X",
                        icon: CupertinoIcons.globe,
                        keyboardType: TextInputType.url,
                        isLast: false,
                      ),
                    ],
                    _Field(
                      controller: _userCtrl,
                      label: "Login",
                      hint: "login",
                      icon: CupertinoIcons.person,
                      isLast: false,
                    ),
                    _Field(
                      controller: _passCtrl,
                      label: "Parol",
                      hint: "••••••••",
                      icon: CupertinoIcons.lock,
                      obscure: _obscure,
                      onToggleObscure: () => setState(() => _obscure = !_obscure),
                      onSubmit: _login,
                      isLast: true,
                    ),
                  ],
                ),
              ),

              // Error
              if (_error != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: IosColors.redFill,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(children: [
                    const Icon(CupertinoIcons.exclamationmark_circle, size: 16, color: IosColors.red),
                    const SizedBox(width: 8),
                    Expanded(child: Text(_error!, style: const TextStyle(fontSize: 14, color: IosColors.red))),
                  ]),
                ),
              ],

              const SizedBox(height: 20),

              // Button
              SizedBox(
                width: double.infinity,
                height: 54,
                child: CupertinoButton(
                  color: IosColors.blue,
                  borderRadius: BorderRadius.circular(14),
                  onPressed: _loading ? null : _login,
                  padding: EdgeInsets.zero,
                  child: _loading
                    ? const CupertinoActivityIndicator(color: Colors.white)
                    : const Text("Kirish",
                        style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600,
                            color: Colors.white, letterSpacing: -0.4)),
                ),
              ),

              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }
}

class _Field extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String hint;
  final IconData icon;
  final bool obscure;
  final bool isLast;
  final TextInputType? keyboardType;
  final VoidCallback? onToggleObscure;
  final VoidCallback? onSubmit;

  const _Field({
    required this.controller,
    required this.label,
    required this.hint,
    required this.icon,
    this.obscure = false,
    this.isLast = false,
    this.keyboardType,
    this.onToggleObscure,
    this.onSubmit,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
          child: Row(children: [
            Icon(icon, size: 17, color: IosColors.blue),
            const SizedBox(width: 12),
            SizedBox(
              width: 72,
              child: Text(label, style: const TextStyle(
                  fontSize: 15, color: IosColors.label)),
            ),
            Expanded(
              child: TextField(
                controller: controller,
                obscureText: obscure,
                keyboardType: keyboardType,
                textInputAction: isLast ? TextInputAction.done : TextInputAction.next,
                onSubmitted: onSubmit != null ? (_) => onSubmit!() : null,
                style: const TextStyle(fontSize: 15, color: IosColors.label),
                decoration: InputDecoration(
                  hintText: hint,
                  hintStyle: const TextStyle(color: IosColors.tertiaryLabel, fontSize: 15),
                  border: InputBorder.none,
                  enabledBorder: InputBorder.none,
                  focusedBorder: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(vertical: 14),
                  suffixIcon: onToggleObscure != null
                    ? GestureDetector(
                        onTap: onToggleObscure,
                        child: Icon(
                          obscure ? CupertinoIcons.eye : CupertinoIcons.eye_slash,
                          size: 18, color: IosColors.gray2,
                        ),
                      )
                    : null,
                ),
              ),
            ),
          ]),
        ),
        if (!isLast)
          const Padding(
            padding: EdgeInsets.only(left: 45),
            child: Divider(height: 1, thickness: 0.5, color: IosColors.separator),
          ),
      ],
    );
  }
}
