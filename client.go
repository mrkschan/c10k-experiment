package main

import (
	"encoding/binary"
	"flag"
	"fmt"
	"net"
	"os"
	"strconv"
	"time"
)

func usage() {
	fmt.Println("Usage: %s [--workers=WORKERS] REQUESTS", os.Args[0])
	os.Exit(0)
}
func argparse() (int, int) {
	var workers int
	flag.IntVar(&workers, "workers", 1,
		"Number of workers to generate requests in parallel")
	flag.Parse()
	requests, err := strconv.Atoi(flag.Arg(0))
	if err != nil {
		usage()
	}

	return workers, requests
}

func send_request() {
	addr, err := net.ResolveTCPAddr("tcp4", "127.0.0.1:8000")
	if err != nil {
		fmt.Println(err.Error())
		return
	}
	conn, err := net.DialTCP("tcp", nil, addr)
	if err != nil {
		fmt.Println(err.Error())
		return
	}

	epoch := time.Now().Unix()

	payload := make([]byte, 8)
	binary.PutVarint(payload, epoch)
	_, err = conn.Write(payload)
	if err != nil {
		fmt.Println(err.Error())
		return
	}

	buffer := make([]byte, 8)
	_, err = conn.Read(buffer)
	if err != nil {
		fmt.Println(err.Error())
	}
	reply, _ := binary.Varint(buffer)

	fmt.Println(reply)
}

func main() {
	workers, requests := argparse()

	queue := make(chan int, requests)
	semaphore := make(chan int, requests)

	// Spawn workers
	for i := 0; i < workers; i++ {
		go func() {
			for {
				<- queue  // Dequeue
				send_request()
				semaphore <- 1  // Mark request as finished
			}
		}()
	}

	// Start sending requests
	for i := 0; i < requests; i++ {
		queue <- i
	}

	// Wait for all requests to be finished
	for i := 0; i < requests; i++ {
		<-semaphore
	}

	os.Exit(0)
}
