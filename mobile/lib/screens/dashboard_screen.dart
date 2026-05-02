import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
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
        final jobId = job["id"] as int;
        try {
          await ApiService.completeJob(jobId);
          setState(() { _printedCount++; _pendingCount--; });
        } catch (e) {
          await ApiService.completeJob(jobId, status: "failed", error: e.toString());
          setState(() { _errorCount++; _pendingCount--; });
        }
      }
    } catch (_) {
      setState(() => _connected = false);
    }
    _polling = false;
  }

  Future<void> _logout() async {
    final ok = await showCupertinoDialog<bool>(
      context: context,
      builder: (_) => CupertinoAlertDialog(
        title: const Text("Chiqish"),
        content: const Text("Tizimdan chiqmoqchimisiz?"),
        actions: [
          CupertinoDialogAction(child: const Text("Bekor"), onPressed: () => Navigator.pop(context, false)),
          CupertinoDialogAction(isDestructiveAction: true, child: const Text("Chiqish"),
              onPressed: () => Navigator.pop(context, true)),
        ],
      ),
    );
    if (ok == true) {
      await ApiService.clearConfig();
      if (mounted) {
        Navigator.of(context).pushReplacement(
          CupertinoPageRoute(builder: (_) => const LoginScreen()),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final bizName = ApiService.businessName.isNotEmpty
        ? ApiService.businessName
        : "Dashboard";

    return Scaffold(
      backgroundColor: IosColors.systemGroupedBg,
      body: CustomScrollView(
        slivers: [
          // Large title nav bar
          CupertinoSliverNavigationBar(
            largeTitle: Text(bizName,
              style: const TextStyle(fontWeight: FontWeight.w700, letterSpacing: -0.5)),
            backgroundColor: IosColors.systemGroupedBg.withValues(alpha: 0.92),
            border: Border.all(color: Colors.transparent),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                CupertinoButton(
                  padding: EdgeInsets.zero,
                  onPressed: _poll,
                  child: const Icon(CupertinoIcons.arrow_clockwise, size: 22),
                ),
                CupertinoButton(
                  padding: EdgeInsets.zero,
                  onPressed: () => Navigator.of(context).push(
                    CupertinoPageRoute(builder: (_) => const SettingsScreen()),
                  ),
                  child: const Icon(CupertinoIcons.settings, size: 22),
                ),
              ],
            ),
          ),

          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
              child: Column(children: [

                // Connection status
                _ConnectionBanner(connected: _connected),
                const SizedBox(height: 20),

                // Stats
                _sectionLabel("Statistika"),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: _StatTile(
                    icon: CupertinoIcons.clock,
                    label: "Kutilmoqda",
                    value: "$_pendingCount",
                    color: IosColors.orange,
                  )),
                  const SizedBox(width: 12),
                  Expanded(child: _StatTile(
                    icon: CupertinoIcons.checkmark_circle_fill,
                    label: "Chop etildi",
                    value: "$_printedCount",
                    color: IosColors.green,
                  )),
                  const SizedBox(width: 12),
                  Expanded(child: _StatTile(
                    icon: CupertinoIcons.xmark_circle_fill,
                    label: "Xatolik",
                    value: "$_errorCount",
                    color: IosColors.red,
                  )),
                ]),
                const SizedBox(height: 24),

                // Info section
                _sectionLabel("Ma'lumotlar"),
                const SizedBox(height: 8),
                _GroupedCard(children: [
                  _InfoRow(
                    icon: CupertinoIcons.building_2_fill,
                    label: "Biznes",
                    value: "#${ApiService.businessId ?? '-'}",
                  ),
                  const Divider(height: 1, thickness: 0.5, indent: 44, color: IosColors.separator),
                  _InfoRow(
                    icon: CupertinoIcons.person_fill,
                    label: "Agent",
                    value: ApiService.username,
                  ),
                  const Divider(height: 1, thickness: 0.5, indent: 44, color: IosColors.separator),
                  _InfoRow(
                    icon: CupertinoIcons.arrow_clockwise,
                    label: "Polling",
                    value: "har 5 soniya",
                  ),
                ]),
                const SizedBox(height: 24),

                // Logout
                _GroupedCard(children: [
                  CupertinoButton(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    onPressed: _logout,
                    child: Row(children: [
                      const Icon(CupertinoIcons.square_arrow_left, color: IosColors.red, size: 20),
                      const SizedBox(width: 12),
                      const Text("Tizimdan chiqish",
                          style: TextStyle(fontSize: 16, color: IosColors.red)),
                      const Spacer(),
                      const Icon(CupertinoIcons.chevron_right,
                          color: IosColors.gray2, size: 16),
                    ]),
                  ),
                ]),

              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionLabel(String text) => Align(
    alignment: Alignment.centerLeft,
    child: Text(text.toUpperCase(),
      style: const TextStyle(
        fontSize: 12, fontWeight: FontWeight.w600,
        color: IosColors.secondaryLabel, letterSpacing: 0.5)),
  );
}

class _ConnectionBanner extends StatelessWidget {
  final bool connected;
  const _ConnectionBanner({required this.connected});

  @override
  Widget build(BuildContext context) {
    final color = connected ? IosColors.green : IosColors.red;
    final fill  = connected ? IosColors.greenFill : IosColors.redFill;
    final icon  = connected ? CupertinoIcons.wifi : CupertinoIcons.wifi_slash;
    final text  = connected ? "Server bilan aloqa bor" : "Server bilan aloqa yo'q";

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(color: fill, borderRadius: BorderRadius.circular(12)),
      child: Row(children: [
        Container(
          width: 32, height: 32,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: color, size: 17),
        ),
        const SizedBox(width: 12),
        Text(text, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: color)),
        const Spacer(),
        Container(
          width: 8, height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
      ]),
    );
  }
}

class _StatTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  const _StatTile({required this.icon, required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
      decoration: BoxDecoration(
        color: IosColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(children: [
        Container(
          width: 36, height: 36,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: color, size: 18),
        ),
        const SizedBox(height: 8),
        Text(value, style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700,
            color: color, letterSpacing: -0.5)),
        const SizedBox(height: 3),
        Text(label, textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 11, color: IosColors.secondaryLabel)),
      ]),
    );
  }
}

class _GroupedCard extends StatelessWidget {
  final List<Widget> children;
  const _GroupedCard({required this.children});

  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(
      color: IosColors.card,
      borderRadius: BorderRadius.circular(12),
    ),
    clipBehavior: Clip.hardEdge,
    child: Column(children: children),
  );
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _InfoRow({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
    child: Row(children: [
      Icon(icon, size: 18, color: IosColors.blue),
      const SizedBox(width: 12),
      Text(label, style: const TextStyle(fontSize: 15, color: IosColors.label)),
      const Spacer(),
      Text(value, style: const TextStyle(fontSize: 15, color: IosColors.secondaryLabel)),
    ]),
  );
}
