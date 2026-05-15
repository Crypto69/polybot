<script setup>
import { useStore } from './composables/useStore.js'
import StatusBar from './components/StatusBar.vue'
import WalletPanel from './components/WalletPanel.vue'
import PnlPanel from './components/PnlPanel.vue'
import StrategyPanel from './components/StrategyPanel.vue'
import EquityCurve from './components/EquityCurve.vue'
import DecisionFeed from './components/DecisionFeed.vue'
import PositionsPanel from './components/PositionsPanel.vue'
import OrdersPanel from './components/OrdersPanel.vue'
import MarketClock from './components/MarketClock.vue'
import StatsFooter from './components/StatsFooter.vue'
import TradeAlertOverlay from './components/TradeAlertOverlay.vue'

const { store, wsStatus, connected } = useStore()
</script>

<template>
  <div class="app">
    <StatusBar :store="store" :connected="connected" :ws-status="wsStatus" />

    <main class="grid">
      <!-- LEFT: wallet → P&L → strategy -->
      <div class="col col-left">
        <WalletPanel :store="store" />
        <PnlPanel :store="store" />
        <StrategyPanel :store="store" />
      </div>

      <!-- CENTER: decision feed (hero) + equity -->
      <div class="col col-center">
        <DecisionFeed :store="store" />
        <EquityCurve :store="store" />
      </div>

      <!-- RIGHT: positions / orders / market clock -->
      <div class="col col-right">
        <PositionsPanel :store="store" />
        <OrdersPanel :store="store" />
        <MarketClock :store="store" />
      </div>
    </main>

    <StatsFooter :store="store" />
    <TradeAlertOverlay />
  </div>
</template>
