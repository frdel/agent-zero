# VTK's loguru has commits beyond 2.1.0

Commits from loguru's master branch have been added into VTK's loguru. They permit to disable signal
handlers. In particular, `loguru::Options::unsafe_signal_handle`, present in loguru 2.1.0, doesn't
exist anymore in VTK. It is replaced by `loguru::Options::signal_options`.
