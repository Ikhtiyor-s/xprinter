import 'package:flutter/material.dart';
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
      title: "Nonbor Print Agent",
      theme: AppTheme.light,
      debugShowCheckedModeBanner: false,
      home: ApiService.isConfigured && ApiService.businessId != null
          ? const DashboardScreen()
          : const LoginScreen(),
    );
  }
}
