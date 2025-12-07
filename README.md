# Local Goods

A web application that helps you find diverse products from local companies based on natural language prompts.

## Features

- **Natural Language Search**: Describe what you're looking for in plain English
- **AI-Powered Filtering**: Uses AI to understand your requirements and find matching products
- **Local Business Focus**: Only shows products from small local companies
- **Credibility Scoring**: Each product is scored based on company credibility (0-100%)
- **Beautiful UI**: Modern, responsive design built with Next.js and shadcn/ui

## Project Structure

```
.
├── flask_api.py              # Flask backend API
├── app.py                    # Original backend logic
├── agent.py                  # AI agent for filter selection
├── url_builder.py            # URL construction logic
├── requirements.txt          # Python dependencies
└── frontend/                 # Next.js frontend
    ├── app/
    │   ├── page.tsx          # Main search page
    │   └── results/          # Results page
    └── components/           # shadcn components
```

## Setup Instructions

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure you have the `emag_filters_and_categories.json` file in the root directory.

3. Start the Flask server:
```bash
python flask_api.py
```

The API will be available at `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. Open `http://localhost:3000` in your browser
2. Enter a description of what you're looking for (e.g., "black wireless headphones under 200 lei")
3. Click "Search Products"
4. Browse the results showing:
   - Product image
   - Product name
   - Company name
   - Credibility score (color-coded: green ≥80%, yellow 60-79%, red <60%)

## API Endpoints

### POST `/api/search`
Search for products based on a prompt.

**Request:**
```json
{
  "prompt": "black wireless headphones under 200 lei"
}
```

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "url": "https://www.emag.ro/...",
      "productName": "Product Name",
      "companyName": "Company Name",
      "credibilityScore": 85,
      "imageUrl": "https://..."
    }
  ],
  "count": 10
}
```

### GET `/api/health`
Health check endpoint.

## Technologies Used

- **Backend**: Flask, BeautifulSoup, Google Generative AI
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui
- **Styling**: Tailwind CSS with custom design system

## Notes

- The backend scrapes eMAG.ro for products and validates companies through listafirme.ro
- Processing may take some time as it validates each company
- Make sure both servers are running for the application to work properly

