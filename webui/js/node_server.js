const express = require('express');
const path = require('path');
const app = express();

const PORT = process.env.NODE_SERVER_PORT || 3000;

app.use(express.static(path.join(__dirname, '../webui'))); 

app.listen(PORT, () => {
  console.log(`Node server running on port ${PORT}`);
});