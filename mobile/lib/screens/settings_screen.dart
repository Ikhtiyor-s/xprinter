import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import 'login_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String _version = '';
  String _buildNumber = '';

  @override
  void initState() {
    super.initState();
    _loadVersion();
  }

  Future<void> _loadVersion() async {
    final info = await PackageInfo.fromPlatform();
    setState(() {
      _version     = info.version;
      _buildNumber = info.buildNumber;
    });
  }

  Future<void> _logout(BuildContext context) async {
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
    if (ok != true) return;
    await ApiService.clearConfig();
    if (context.mounted) {
      Navigator.of(context).pushAndRemoveUntil(
        CupertinoPageRoute(builder: (_) => const LoginScreen()), (_) => false,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: IosColors.systemGroupedBg,
      body: CustomScrollView(
        slivers: [
          CupertinoSliverNavigationBar(
            largeTitle: const Text("Sozlamalar",
              style: TextStyle(fontWeight: FontWeight.w700, letterSpacing: -0.5)),
            backgroundColor: IosColors.systemGroupedBg.withValues(alpha: 0.92),
            border: Border.all(color: Colors.transparent),
            leading: CupertinoButton(
              padding: EdgeInsets.zero,
              onPressed: () => Navigator.of(context).pop(),
              child: const Icon(CupertinoIcons.chevron_left, size: 22),
            ),
          ),

          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
              child: Column(children: [

                // Hisob
                _sectionLabel("Hisob"),
                const SizedBox(height: 8),
                Container(
                  decoration: BoxDecoration(
                    color: IosColors.card,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(children: [
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(children: [
                        Container(
                          width: 48, height: 48,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [IosColors.blue, IosColors.indigo],
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                            ),
                            shape: BoxShape.circle,
                          ),
                          child: Center(
                            child: Text(
                              ApiService.username.isNotEmpty
                                ? ApiService.username[0].toUpperCase()
                                : "A",
                              style: const TextStyle(color: Colors.white, fontSize: 20,
                                  fontWeight: FontWeight.w700),
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(ApiService.username,
                              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600,
                                  color: IosColors.label)),
                            const SizedBox(height: 2),
                            Text("Biznes #${ApiService.businessId ?? '-'} · ${ApiService.businessName}",
                              style: const TextStyle(fontSize: 13, color: IosColors.secondaryLabel),
                              overflow: TextOverflow.ellipsis),
                          ]),
                        ),
                      ]),
                    ),
                    const Divider(height: 1, thickness: 0.5, indent: 16, color: IosColors.separator),
                    _SettingsRow(
                      icon: CupertinoIcons.square_arrow_left,
                      iconColor: IosColors.red,
                      label: "Tizimdan chiqish",
                      labelColor: IosColors.red,
                      onTap: () => _logout(context),
                      showChevron: true,
                    ),
                  ]),
                ),
                const SizedBox(height: 24),

                // Ilova haqida
                _sectionLabel("Ilova haqida"),
                const SizedBox(height: 8),
                Container(
                  decoration: BoxDecoration(
                    color: IosColors.card,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(children: [
                    _SettingsRow(
                      icon: CupertinoIcons.app_badge,
                      iconColor: IosColors.blue,
                      label: "Nonbor Print Agent",
                      value: _version.isNotEmpty ? "v$_version" : "",
                    ),
                    const Divider(height: 1, thickness: 0.5, indent: 52, color: IosColors.separator),
                    _SettingsRow(
                      icon: CupertinoIcons.hammer,
                      iconColor: IosColors.gray,
                      label: "Build",
                      value: _buildNumber.isNotEmpty ? "#$_buildNumber" : "",
                    ),
                    const Divider(height: 1, thickness: 0.5, indent: 52, color: IosColors.separator),
                    _SettingsRow(
                      icon: CupertinoIcons.printer_fill,
                      iconColor: IosColors.indigo,
                      label: "Chop etish agenti",
                      value: "nonbor.uz",
                    ),
                  ]),
                ),
                const SizedBox(height: 32),

                // Versiya pastda katta ko'rsatiladi
                if (_version.isNotEmpty)
                  Column(children: [
                    Text("v$_version",
                      style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700,
                          color: IosColors.label, letterSpacing: -0.5)),
                    const SizedBox(height: 4),
                    Text("Nonbor Print Agent",
                      style: const TextStyle(fontSize: 13, color: IosColors.secondaryLabel)),
                    const SizedBox(height: 4),
                    Text("Build $_buildNumber",
                      style: const TextStyle(fontSize: 12, color: IosColors.tertiaryLabel)),
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
      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
          color: IosColors.secondaryLabel, letterSpacing: 0.5)),
  );
}

class _SettingsRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final Color? labelColor;
  final String? value;
  final VoidCallback? onTap;
  final bool showChevron;

  const _SettingsRow({
    required this.icon,
    required this.iconColor,
    required this.label,
    this.labelColor,
    this.value,
    this.onTap,
    this.showChevron = false,
  });

  @override
  Widget build(BuildContext context) {
    return CupertinoButton(
      padding: EdgeInsets.zero,
      onPressed: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(children: [
          Container(
            width: 30, height: 30,
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(7),
            ),
            child: Icon(icon, color: iconColor, size: 16),
          ),
          const SizedBox(width: 14),
          Expanded(child: Text(label,
              style: TextStyle(fontSize: 16, color: labelColor ?? IosColors.label))),
          if (value != null && value!.isNotEmpty)
            Text(value!, style: const TextStyle(fontSize: 15, color: IosColors.secondaryLabel)),
          if (showChevron || onTap != null)
            const Padding(
              padding: EdgeInsets.only(left: 6),
              child: Icon(CupertinoIcons.chevron_right, color: IosColors.gray2, size: 14),
            ),
        ]),
      ),
    );
  }
}
