import 'package:flutter/material.dart';

class IosColors {
  // System Colors
  static const blue    = Color(0xFF007AFF);
  static const green   = Color(0xFF34C759);
  static const red     = Color(0xFFFF3B30);
  static const orange  = Color(0xFFFF9500);
  static const indigo  = Color(0xFF5856D6);
  static const gray    = Color(0xFF8E8E93);
  static const gray2   = Color(0xFFAEAEB2);
  static const gray6   = Color(0xFFF2F2F7);

  // Backgrounds
  static const systemBg        = Color(0xFFF2F2F7);
  static const systemGroupedBg = Color(0xFFEFEFF4);
  static const card            = Color(0xFFFFFFFF);
  static const separator       = Color(0xFFC6C6C8);

  // Text
  static const label           = Color(0xFF000000);
  static const secondaryLabel  = Color(0xFF8E8E93);
  static const tertiaryLabel   = Color(0xFFC7C7CC);

  // Tinted fills
  static const blueFill   = Color(0x1A007AFF);
  static const greenFill  = Color(0x1A34C759);
  static const redFill    = Color(0x1AFF3B30);

  // Backward compat
  static const primary          = blue;
  static const primaryDark      = Color(0xFF0062CC);
  static const bg               = systemBg;
  static const text             = label;
  static const textSecondary    = secondaryLabel;
  static const success          = green;
  static const error            = red;
  static const pending          = blue;
  static const accent           = indigo;
}

// Alias
typedef AppColors = IosColors;

class AppTheme {
  static ThemeData get light {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(
        seedColor: IosColors.blue,
        brightness: Brightness.light,
        surface: IosColors.card,
      ),
      scaffoldBackgroundColor: IosColors.systemBg,
      fontFamily: '.SF Pro Text',
      textTheme: _textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: IosColors.systemGroupedBg,
        foregroundColor: IosColors.label,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        shadowColor: IosColors.separator,
        centerTitle: false,
        titleTextStyle: const TextStyle(
          fontFamily: '.SF Pro Display',
          fontSize: 17,
          fontWeight: FontWeight.w600,
          color: IosColors.label,
          letterSpacing: -0.4,
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: IosColors.card,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: IosColors.blue,
          foregroundColor: Colors.white,
          elevation: 0,
          shadowColor: Colors.transparent,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(
            fontFamily: '.SF Pro Text',
            fontSize: 17,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.4,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: IosColors.card,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: IosColors.separator, width: 0.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: IosColors.separator, width: 0.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: IosColors.blue, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        hintStyle: const TextStyle(color: IosColors.tertiaryLabel),
      ),
      listTileTheme: const ListTileThemeData(
        tileColor: IosColors.card,
        shape: RoundedRectangleBorder(),
      ),
      dividerTheme: const DividerThemeData(
        color: IosColors.separator,
        thickness: 0.5,
        indent: 16,
      ),
    );
  }

  static const _textTheme = TextTheme(
    displayLarge: TextStyle(fontFamily: '.SF Pro Display', fontSize: 34, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: IosColors.label),
    headlineLarge: TextStyle(fontFamily: '.SF Pro Display', fontSize: 28, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: IosColors.label),
    headlineMedium: TextStyle(fontFamily: '.SF Pro Display', fontSize: 22, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: IosColors.label),
    titleLarge: TextStyle(fontFamily: '.SF Pro Display', fontSize: 17, fontWeight: FontWeight.w600, letterSpacing: -0.4, color: IosColors.label),
    titleMedium: TextStyle(fontFamily: '.SF Pro Text', fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.3, color: IosColors.label),
    bodyLarge: TextStyle(fontFamily: '.SF Pro Text', fontSize: 17, fontWeight: FontWeight.w400, letterSpacing: -0.4, color: IosColors.label),
    bodyMedium: TextStyle(fontFamily: '.SF Pro Text', fontSize: 15, fontWeight: FontWeight.w400, letterSpacing: -0.2, color: IosColors.label),
    bodySmall: TextStyle(fontFamily: '.SF Pro Text', fontSize: 13, fontWeight: FontWeight.w400, color: IosColors.secondaryLabel),
    labelLarge: TextStyle(fontFamily: '.SF Pro Text', fontSize: 15, fontWeight: FontWeight.w500, letterSpacing: -0.2, color: IosColors.blue),
  );
}
