const String kFlavor = String.fromEnvironment('FLAVOR', defaultValue: 'prod');
const bool kIsTest = kFlavor == 'test';
