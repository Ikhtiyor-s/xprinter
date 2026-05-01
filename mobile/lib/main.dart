import 'package:flutter/material.dart';
import 'config/flavor.dart';
import 'theme/app_theme.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiService.loadConfig();
  runApp(const NonborPrintApp());
}

class NonborPrintApp extends StatelessWidget {
  const NonborPrintApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: kIsTest ? "Nonbor Print Agent [TEST]" : "Nonbor Print Agent",
      theme: AppTheme.light,
      debugShowCheckedModeBanner: false,
      builder: (context, child) => kIsTest
          ? Stack(children: [
              child!,
              Positioned(
                top: 0, left: 0,
                child: SafeArea(
                  child: Container(
                    margin: const EdgeInsets.all(6),
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: Colors.red,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'TEST',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                ),
              ),
            ])
          : child!,
      home: ApiService.isConfigured && ApiService.businessId != null
          ? const DashboardScreen()
          : const LoginScreen(),
    );
  }
}
