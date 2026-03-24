import { createRouter, createWebHashHistory } from "vue-router";

let routes = [
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/auth/AuthView.vue')
    },
    {
        path: '/',
        name: 'Chat',
        component: () => import('../views/chat/index.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/knowledge-visualization',
        name: 'KnowledgeVisualization',
        component: () => import('../views/knowledge/index.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/teaching-visualization',
        name: 'TeachingVisualization',
        component: () => import('../views/dashboard/index.vue'),
        meta: { requiresAuth: true }
    }
]
const router = createRouter({
    history: createWebHashHistory(),
    routes
})

router.beforeEach((to, from, next) => {
    const user = localStorage.getItem('tablesage-user')
    if (to.meta.requiresAuth && !user) {
        next('/login')
    } else {
        next()
    }
})

export default router 
