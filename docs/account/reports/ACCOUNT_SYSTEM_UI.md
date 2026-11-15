# Account UI

## Entry point

The existing Jarvis profile card/icon opens `AccountCenterDialog`. It is not a mandatory startup page. The existing local profile editor remains available from the Settings account section and is not treated as authentication.

## Local Panel

When no server account is present, the panel displays the actual `LOCAL_ONLY` state, “аккаунт не подключён”, synchronization “не настроена”, and that Jarvis works locally. Actions are Login, Create Account, Password Recovery and Continue in Local Mode. No cloud state is invented.

## Forms

`AccountLoginDialog`, `AccountRegisterDialog`, `EmailVerificationDialog` and `PasswordResetDialog` use the existing PySide6 stack and the Jarvis dark/glass visual language. They provide email/password validation, password visibility, confirmation checks, progress/status messaging and honest server-unavailable errors. Legal consent is not auto-checked and no legal text is invented.

The future account state view is represented by the same context boundary. Until a verified provider exists, email, devices and last-sync data are not displayed as if real.

## Failure behavior

Account UI failures do not enter the chat pipeline and do not block Local Mode. Closing the panel or choosing Continue in Local Mode leaves local history untouched. The UI never uploads local data or invokes an import automatically.

