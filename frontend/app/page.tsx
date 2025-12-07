'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Search, Loader2 } from 'lucide-react'

export default function Home() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim() || loading) return

    setLoading(true)
    try {
      const response = await fetch('http://localhost:5000/api/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt }),
      })

      const data = await response.json()
      
      if (data.success) {
        // Store results in sessionStorage and navigate to results page
        sessionStorage.setItem('searchResults', JSON.stringify(data.products))
        router.push('/results')
      } else {
        alert('Error: ' + (data.error || 'Failed to search products'))
      }
    } catch (error) {
      console.error('Error:', error)
      alert('Failed to connect to server. Make sure the Flask API is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
      <div className="w-full max-w-4xl">
        <div className="text-center mb-12">
          <h1 className="text-6xl font-bold text-gray-900 mb-4">
            Local Goods
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Giving you the best option for diverse products made by local companies
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="relative">
              <Input
                type="text"
                placeholder="Describe what you're looking for... (e.g., 'black wireless headphones under 200 lei')"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full h-14 text-lg pr-12 pl-4 border-2 border-gray-200 focus:border-blue-500 rounded-xl"
                disabled={loading}
              />
              <Search className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            </div>
            <Button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="w-full h-12 text-lg font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Searching...
                </>
              ) : (
                'Search Products'
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}

