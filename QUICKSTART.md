# Quick Start Guide

## Prerequisites
- Python 3.8+ installed
- Node.js 18+ and npm installed
- Google Generative AI API key (already configured in `agent.py`)

## Step-by-Step Setup

### 1. Install Backend Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Flask Backend
Open a terminal and run:
```bash
python flask_api.py
```
You should see:
```
 * Running on http://127.0.0.1:5000
```

### 3. Install Frontend Dependencies
Open a **new terminal** and navigate to the frontend directory:
```bash
cd frontend
npm install
```

### 4. Start the Frontend
In the same terminal (still in the `frontend` directory):
```bash
npm run dev
```
You should see:
```
  ▲ Next.js 14.x.x
  - Local:        http://localhost:3000
```

### 5. Open the Application
Open your browser and go to: **http://localhost:3000**

## Testing

1. On the main page, try entering a search like:
   - "black wireless headphones under 200 lei"
   - "laptop bag for business"
   - "organic coffee beans"

2. Click "Search Products" and wait for results

3. The results page will show:
   - Product images
   - Product names
   - Company names
   - Credibility scores (color-coded)

## Troubleshooting

**Frontend can't connect to backend:**
- Make sure Flask is running on port 5000
- Check that CORS is enabled (it should be by default)

**No products found:**
- The search may take a while (30-60 seconds) as it validates companies
- Try a different search query
- Check the Flask terminal for error messages

**Images not loading:**
- Some products may not have images available
- This is normal and the UI will show "No Image" placeholder

