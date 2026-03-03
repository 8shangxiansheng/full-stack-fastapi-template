import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Clock3, ShoppingCart, Soup } from "lucide-react"
import { Suspense } from "react"

import { DashboardService } from "@/client"
import PendingItems from "@/components/Pending/PendingItems"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - FastAPI Template",
      },
    ],
  }),
})

function Dashboard() {
  return (
    <Suspense fallback={<PendingItems />}>
      <DashboardContent />
    </Suspense>
  )
}

function formatAmount(value: string | number) {
  const amount = typeof value === "string" ? Number(value) : value
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00"
}

function getDashboardQueryOptions() {
  return {
    queryFn: () => DashboardService.readDashboardOverview(),
    queryKey: ["dashboard-overview"],
  }
}

function DashboardContent() {
  const { user: currentUser } = useAuth()
  const { data } = useSuspenseQuery(getDashboardQueryOptions())
  const orderHighlights = data.orders.status_breakdown.filter(
    (item) => item.count > 0,
  )
  const paymentHighlights = data.payments.status_breakdown.filter(
    (item) => item.count > 0,
  )

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl truncate max-w-sm">
          Hi, {currentUser?.full_name || currentUser?.email} 👋
        </h1>
        <p className="text-muted-foreground">
          Local demo dashboard ({data.scope === "all" ? "all data" : "my data"})
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button asChild>
          <Link to="/items">
            <Soup className="size-4" />
            Browse Menu
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/cart">
            <ShoppingCart className="size-4" />
            Open Cart
          </Link>
        </Button>
        <Button asChild variant="secondary">
          <Link to="/orders">
            <Clock3 className="size-4" />
            View Orders
          </Link>
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Menu</CardTitle>
            <CardDescription>Published content overview</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>
              Categories: {data.menu.categories_active}/
              {data.menu.categories_total}
            </p>
            <p>
              Dishes: {data.menu.dishes_active}/{data.menu.dishes_total}
            </p>
            <p>
              SKUs: {data.menu.skus_active}/{data.menu.skus_total}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Cart & Address</CardTitle>
            <CardDescription>Current account context</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Cart items: {data.cart.items_count}</p>
            <p>Cart total: ¥ {formatAmount(data.cart.total_amount)}</p>
            <p>Addresses: {data.addresses.total}</p>
            <p>Default addresses: {data.addresses.default_count}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Orders</CardTitle>
            <CardDescription>Lifecycle snapshot</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Total: {data.orders.total}</p>
            <p>Today: {data.orders.today}</p>
            <p>Realized GMV: ¥ {formatAmount(data.orders.realized_gmv)}</p>
            <div className="flex flex-wrap gap-1">
              {orderHighlights.length === 0 ? (
                <Badge variant="outline">No orders</Badge>
              ) : (
                orderHighlights.map((item) => (
                  <Badge key={item.status} variant="secondary">
                    {item.status}: {item.count}
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Payments</CardTitle>
            <CardDescription>Collection status</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Total: {data.payments.total}</p>
            <p>
              Success amount: ¥ {formatAmount(data.payments.success_amount)}
            </p>
            <div className="flex flex-wrap gap-1">
              {paymentHighlights.length === 0 ? (
                <Badge variant="outline">No payments</Badge>
              ) : (
                paymentHighlights.map((item) => (
                  <Badge key={item.status} variant="secondary">
                    {item.status}: {item.count}
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Orders</CardTitle>
          <CardDescription>Latest 5 orders in current scope</CardDescription>
        </CardHeader>
        <CardContent>
          {data.recent_orders.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recent orders</p>
          ) : (
            <div className="space-y-2">
              {data.recent_orders.map((order) => (
                <div
                  key={order.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div>
                    <p className="font-medium">{order.order_no}</p>
                    <p className="text-xs text-muted-foreground">
                      {order.status}
                    </p>
                  </div>
                  <p className="font-semibold">
                    ¥ {formatAmount(order.total_amount)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
