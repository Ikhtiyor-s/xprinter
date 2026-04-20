import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import 'login_screen.dart';
import 'settings_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _polling = false;
  bool _connected = false;
  int _pendingCount = 0;
  int _printedCount = 0;
  int _errorCount = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _checkConnection();
    _startPolling();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _checkConnection() async {
    try {
      await ApiService.healthCheck();
      setState(() => _connected = true);
    } catch (_) {
      setState(() => _connected = false);
    }
  }

  void _startPolling() {
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _poll());
    _poll();
  }

  Future<void> _poll() async {
    if (_polling) return;
    _polling = true;
    try {
      final jobs = await ApiService.pollJobs();
      setState(() {
        _pendingCount = jobs.length;
        _connected = true;
      });
      for (final job in jobs) {
        final jobId = job["job_id"];
        try {
          await ApiService.completeJob(jobId);
          setState(() { _printedCount++; _pendingCount--; });
        } catch (e) {
          await ApiService.completeJob(jobId, action: "failed", error: e.toString());
          setState(() { _errorCount++; _pendingCount--; });
        }
      }
    } catch (_) {
      setState(() => _connected = false);
    }
    _polling = false;
  }

  void _logout() async {
    await ApiService.clearConfig();
    if (mounted) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(ApiService.businessName.isNotEmpty ? ApiService.businessName : "Dashboard"),
        actions: [
          IconButton(icon: const Icon(Icons.settings), onPressed: () {
            Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SettingsScreen()));
          }),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _poll,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Connection status
            _StatusCard(connected: _connected).animate().fadeIn(duration: 300.ms),
            const SizedBox(height: 16),

            // Stats row
            Row(children: [
              Expanded(child: _StatCard(icon: Icons.hourglass_top, label: "Kutilmoqda", value: "$_pendingCount", color: AppColors.pending)),
              const SizedBox(width: 12),
              Expanded(child: _StatCard(icon: Icons.check_circle, label: "Chop etildi", value: "$_printedCount", color: AppColors.success)),
              const SizedBox(width: 12),
              Expanded(child: _StatCard(icon: Icons.error, label: "Xatolik", value: "$_errorCount", color: AppColors.error)),
            ]).animate().slideY(begin: 0.05, duration: 300.ms).fadeIn(),
            const SizedBox(height: 24),

            // Info
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text("Ma'lumotlar", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 12),
                _InfoRow(icon: Icons.business, label: "Biznes ID", value: "#${ApiService.businessId ?? '-'}"),
                _InfoRow(icon: Icons.person, label: "Agent", value: ApiService.username),
              ]),
            ).animate().slideY(begin: 0.05, delay: 100.ms, duration: 300.ms).fadeIn(),
            const SizedBox(height: 24),

            // Logout
            OutlinedButton.icon(
              onPressed: _logout,
              icon: const Icon(Icons.logout, color: AppColors.error),
              label: const Text("Chiqish", style: TextStyle(color: AppColors.error)),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14),
                side: const BorderSide(color: AppColors.error),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final bool connected;
  const _StatusCard({required this.connected});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: connected ? AppColors.success.withValues(alpha: 0.1) : AppColors.error.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: connected ? AppColors.success.withValues(alpha: 0.3) : AppColors.error.withValues(alpha: 0.3)),
      ),
      child: Row(children: [
        Container(
          width: 12, height: 12,
          decoration: BoxDecoration(shape: BoxShape.circle, color: connected ? AppColors.success : AppColors.error),
        ),
        const SizedBox(width: 12),
        Text(connected ? "Server bilan aloqa bor" : "Server bilan aloqa yo'q",
          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: connected ? AppColors.success : AppColors.error)),
      ]),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  const _StatCard({required this.icon, required this.label, required this.value, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(children: [
        Icon(icon, color: color, size: 28),
        const SizedBox(height: 8),
        Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: color)),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
      ]),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _InfoRow({required this.icon, required this.label, required this.value});
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        Icon(icon, size: 18, color: AppColors.textSecondary),
        const SizedBox(width: 10),
        Text("$label: ", style: const TextStyle(color: AppColors.textSecondary, fontSize: 14)),
        Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14), overflow: TextOverflow.ellipsis)),
      ]),
    );
  }
}
