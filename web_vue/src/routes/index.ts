import { createRouter, createWebHashHistory } from "vue-router";
 
let routes= [
    {
        path: '/',
        name: 'Chat',
        component: () => import('../components/MainChat.vue')
    },
    {
        path: '/knowledge-visualization',
        name: 'KnowledgeVisualization',
        component: () => import('../components/knowledge-visualization.vue')
    },
    {
        path: '/teaching-visualization',
        name: 'TeachingVisualization',
        component: () => import('../components/teaching-visualization.vue')
    }
]
const router = createRouter({
    history: createWebHashHistory(),
    routes
})
export default router 
