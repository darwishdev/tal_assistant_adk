//go:build ignore

// debug_subscribe.go — subscribe to both Redis channels and print messages
// Run with: go run debug_subscribe.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"
)

func redisAddr() string {
	if u := os.Getenv("REDIS_URL"); u != "" {
		return u
	}
	return "localhost:6379"
}

func channel(env, fallback string) string {
	if v := os.Getenv(env); v != "" {
		return v
	}
	return fallback
}

func main() {
	nqiCh := channel("NQI_CHANNEL", "nqi:results")
	signalCh := channel("SIGNAL_CHANNEL", "signal:results")

	client := redis.NewClient(&redis.Options{Addr: redisAddr()})
	defer client.Close()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Verify connection
	if err := client.Ping(ctx).Err(); err != nil {
		log.Fatalf("redis ping failed: %v", err)
	}
	fmt.Printf("connected to Redis at %s\n", redisAddr())
	fmt.Printf("  listening on NQI channel    → %s\n", nqiCh)
	fmt.Printf("  listening on signal channel → %s\n\n", signalCh)

	pubsub := client.Subscribe(ctx, nqiCh, signalCh)
	defer pubsub.Close()

	ch := pubsub.Channel()
	for {
		select {
		case <-ctx.Done():
			fmt.Println("\nshutting down")
			return

		case msg, ok := <-ch:
			if !ok {
				fmt.Println("channel closed")
				return
			}
			printMessage(msg)
		}
	}
}

func printMessage(msg *redis.Message) {
	ts := time.Now().Format("15:04:05.000")

	// Pretty-print JSON if possible, otherwise raw
	var pretty any
	if err := json.Unmarshal([]byte(msg.Payload), &pretty); err == nil {
		b, _ := json.MarshalIndent(pretty, "    ", "  ")
		fmt.Printf("[%s] channel=%s\n    %s\n\n", ts, msg.Channel, b)
	} else {
		fmt.Printf("[%s] channel=%s\n    %s\n\n", ts, msg.Channel, msg.Payload)
	}
}
