import { createApp } from 'vue'
import App from './App.vue'
 
 //routes
 import router from "./routes/index"; 

import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  BarChart,
  LineChart,
  PieChart,
  CanvasRenderer
])
 
const app= createApp(App)
 
//routes 
app.use(router)  
app.mount('#app')