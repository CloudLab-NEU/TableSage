import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

import AutoImport from "unplugin-auto-import/vite";
import Components from 'unplugin-vue-components/vite';


// https://vite.dev/config/
export default defineConfig({
  base: './', 
  plugins: [
		vue(),
		AutoImport({
			imports: ['vue', 'vue-router'],
			dts: "src/auto-import.d.ts",
		}),
		Components({
            dts: "src/components.d.ts",
		})
	],
	build: {
      emptyOutDir: true, 
	  outDir: 'dist',
    },
})
