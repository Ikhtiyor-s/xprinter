import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import 'login_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _serverCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _serverCtrl.text = ApiService.serverUrl;
  }

  void _save() async {
    await ApiService.saveConfig(serverUrl: _serverCtrl.text.trim());
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Saqlandi"), backgroundColor: AppColors.success),
      );
      Navigator.pop(context);
    }
  }

  void _logout() async {
    await ApiService.clearConfig();
    if (mounted) {
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const LoginScreen()), (_) => false,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Sozlamalar")),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text("Server", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const SizedBox(height: 12),
              TextField(controller: _serverCtrl, decoration: const InputDecoration(labelText: "Server URL", prefixIcon: Icon(Icons.dns_outlined))),
              const SizedBox(height: 16),
              SizedBox(width: double.infinity, height: 48, child: ElevatedButton.icon(
                onPressed: _save, icon: const Icon(Icons.save), label: const Text("Saqlash"),
              )),
            ]),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text("Hisob", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              ListTile(
                leading: const CircleAvatar(backgroundColor: AppColors.primary, child: Icon(Icons.person, color: Colors.white)),
                title: Text(ApiService.username, style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text("Biznes #${ApiService.businessId ?? '-'} - ${ApiService.businessName}"),
              ),
              const Divider(),
              ListTile(
                leading: const Icon(Icons.logout, color: AppColors.error),
                title: const Text("Tizimdan chiqish", style: TextStyle(color: AppColors.error)),
                onTap: _logout,
              ),
            ]),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
            child: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text("Ilova haqida", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              SizedBox(height: 8),
              Text("Nonbor Print Agent v1.0.0", style: TextStyle(color: AppColors.textSecondary)),
              SizedBox(height: 4),
              Text("Buyurtmalarni avtomatik chop etish", style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
            ]),
          ),
        ],
      ),
    );
  }
}
