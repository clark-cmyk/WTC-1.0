/**
 * js/03_blackboard.js
 * Shared State Bus for WTC 1.0
 * Goldman Prop Desk Standards
 */

'use strict';

window.BLACKBOARD = {
    state: {},
    subscribers: new Map(),
    setState: function(key, value) {
        this.state[key] = value;
        console.log(`[BLACKBOARD] Updated: ${key}`);
        this.notify(key);
    },
    getState: function(key) {
        return this.state[key];
    },
    subscribe: function(key, callback) {
        if (!this.subscribers.has(key)) this.subscribers.set(key, []);
        this.subscribers.get(key).push(callback);
        if (this.state[key] !== undefined) callback(this.state[key]);
    },
    notify: function(key) {
        const subs = this.subscribers.get(key);
        if (subs) subs.forEach(cb => cb(this.state[key]));
    }
};

console.log("Blackboard Bus Loaded.");