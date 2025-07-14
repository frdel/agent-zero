import React from 'react';
import Login from './components/Login';
import useAuth from './store/authStore';
import NoiseOverlay from './components/NoiseOverlay';
import Watermark from './components/Watermark';

const App: React.FC = () => {
  const authenticated = useAuth((s) => s.authenticated);

  return (
    <div className="app-shell">
      <NoiseOverlay />
      <Watermark text="agent0range" />
      {!authenticated ? <Login /> : (
        <div className="main-content">
          <h1>Welcome to agent0range</h1>
          {/* Main app content goes here */}
        </div>
      )}
    </div>
  );
};

export default App;
