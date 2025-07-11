import React, { useState } from 'react';
import useAuth from '../store/authStore';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const login = useAuth((s) => s.login);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Replace with real API call
    if (username === 'admin' && password === 'agent0range') {
      login();
    } else {
      setError('Invalid credentials');
    }
  };

  return (
    <div className="login-shell">
      <form className="login-form" onSubmit={handleSubmit} autoComplete="off">
        <h1>agent0range Secure Login</h1>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
          autoFocus
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
        />
        <button type="submit">Login</button>
        {error && <div className="error-msg">{error}</div>}
      </form>
    </div>
  );
};

export default Login;
