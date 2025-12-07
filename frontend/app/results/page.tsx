'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ArrowLeft, ExternalLink, ShoppingCart } from 'lucide-react'

interface Product {
  url: string
  productName: string
  companyName: string
  credibilityScore: number
  imageUrl: string
  price: number | null
}

export default function ResultsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  const addToCart = (product: Product) => {
    const cart = JSON.parse(localStorage.getItem('cart') || '[]')
    const existingIndex = cart.findIndex((item: Product) => item.url === product.url)
    
    if (existingIndex >= 0) {
      cart[existingIndex].quantity = (cart[existingIndex].quantity || 1) + 1
    } else {
      cart.push({ ...product, quantity: 1 })
    }
    
    localStorage.setItem('cart', JSON.stringify(cart))
    alert('Product added to cart!')
  }

  useEffect(() => {
    const storedResults = sessionStorage.getItem('searchResults')
    if (storedResults) {
      setProducts(JSON.parse(storedResults))
      setLoading(false)
    } else {
      router.push('/')
    }
  }, [router])

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-50 border-green-200'
    if (score >= 60) return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    return 'text-red-600 bg-red-50 border-red-200'
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading results...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <Button
              variant="ghost"
              onClick={() => router.push('/')}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Search
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/cart')}
            >
              <ShoppingCart className="mr-2 h-4 w-4" />
              Cart
            </Button>
          </div>
          <h2 className="text-3xl font-bold text-gray-900">
            Found {products.length} Products
          </h2>
          <p className="text-gray-600 mt-2">
            Products from local companies matching your criteria
          </p>
        </div>

        {products.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-gray-600">
                No products found. Try a different search.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {products.map((product, index) => (
              <Card key={index} className="overflow-hidden hover:shadow-lg transition-shadow flex flex-col">
                <div className="relative h-64 w-full bg-gray-100 flex-shrink-0">
                  {product.imageUrl ? (
                    <img
                      src={product.imageUrl}
                      alt={product.productName}
                      className="w-full h-full object-contain"
                      onError={(e) => {
                        const target = e.target as HTMLImageElement
                        target.style.display = 'none'
                        const parent = target.parentElement
                        if (parent && !parent.querySelector('.placeholder')) {
                          const placeholder = document.createElement('div')
                          placeholder.className = 'placeholder flex items-center justify-center h-full text-gray-400'
                          placeholder.textContent = 'No Image'
                          parent.appendChild(placeholder)
                        }
                      }}
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-400">
                      No Image
                    </div>
                  )}
                </div>
                <CardHeader className="flex-shrink-0">
                  <CardTitle className="text-lg line-clamp-2 min-h-[3rem]">
                    {product.productName}
                  </CardTitle>
                  <CardDescription className="text-base">
                    {product.companyName}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col justify-between">
                  <div className="space-y-3">
                    {product.price !== null && product.price !== undefined && typeof product.price === 'number' && (
                      <div className="text-2xl font-bold text-purple-600">
                        {product.price.toFixed(2)} RON
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <div className={`px-4 py-2 rounded-lg border-2 font-bold text-lg ${getScoreColor(product.credibilityScore)}`}>
                        {product.credibilityScore}%
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => window.open(product.url, '_blank')}
                        >
                          <ExternalLink className="mr-2 h-4 w-4" />
                          View
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => addToCart(product)}
                          className="bg-purple-600 hover:bg-purple-700"
                        >
                          <ShoppingCart className="mr-2 h-4 w-4" />
                          Add to Cart
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

