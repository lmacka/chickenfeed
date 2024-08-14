const express = require('express');
const fetch = require('node-fetch');
const app = express();
const port = 3000;

app.use(express.static('public')); // Serve static files from the 'public' directory

app.post('/give-treat', async (req, res) => {
  try {
    const response = await fetch('http://localhost:3080/cycle', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ servo: 'servo1' })
    });

    if (response.ok) {
      console.log('Treat given to the chickens!');
      res.sendStatus(200);
    } else {
      console.error('Failed to give treat.');
      res.sendStatus(500);
    }
  } catch (error) {
    console.error('Error:', error);
    res.sendStatus(500);
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});