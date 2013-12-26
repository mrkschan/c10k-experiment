package main

import (
	"encoding/binary"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"strconv"
	"time"
)

func usage() {
	msg := "Usage: %s [--workers=WORKERS --verbose] REQUESTS"
	fmt.Println(msg, os.Args[0])
	os.Exit(0)
}
func argparse() (int, int, bool) {
	var (
		workers int
		verbose bool
	)
	flag.IntVar(&workers, "workers", 1,
		"Number of workers to generate requests in parallel")
	flag.BoolVar(&verbose, "verbose", false, "Log error to stderr")
	flag.Parse()
	requests, err := strconv.Atoi(flag.Arg(0))
	if err != nil {
		usage()
	}

	return workers, requests, verbose
}

func send_request(verbose bool) int64 {
	const (
		DNS_ERR   = -1
		SOCK_ERR  = -2
		WRITE_ERR = -3
		READ_ERR  = -4
		SVR_ERR   = -5
	)

	addr, err := net.ResolveTCPAddr("tcp4", "127.0.0.1:8000")
	if err != nil {
		if verbose {
			log.Println(err)
		}
		return DNS_ERR
	}
	conn, err := net.DialTCP("tcp", nil, addr)
	if err != nil {
		if verbose {
			log.Println(err)
		}
		return SOCK_ERR
	}
	defer conn.Close()

	start := time.Now().UnixNano()

	epoch := time.Now().Unix()
	payload := make([]byte, 8)
	binary.PutVarint(payload, epoch)
	_, err = conn.Write(payload)
	if err != nil {
		if verbose {
			log.Println(err)
		}
		return WRITE_ERR
	}

	buffer := make([]byte, 8)
	_, err = conn.Read(buffer)
	if err != nil {
		if verbose {
			log.Println(err)
		}
		return READ_ERR
	}

	reply, _ := binary.Varint(buffer)
	if reply != epoch {
		if verbose {
			msg := "Integrity error - reply: %d, epoch: %d"
			log.Printf(msg, reply, epoch)
		}
		return SVR_ERR
	}

	finish := time.Now().UnixNano()
	return (finish - start) / 1e6 // in ms.
}

func main() {
	workers, requests, verbose := argparse()

	queue := make(chan int, requests)
	semaphore := make(chan int, requests)
	results := make(chan int64, requests)

	// Spawn workers
	for i := 0; i < workers; i++ {
		go func() {
			for {
				<-queue // Dequeue task
				results <- send_request(verbose)
				semaphore <- 1 // Mark request as finished
			}
		}()
	}

	// Start sending requests
	start := time.Now().UnixNano()
	for i := 0; i < requests; i++ {
		queue <- i
	}

	// Wait for all requests to be finished
	for i := 0; i < requests; i++ {
		<-semaphore
	}
	finish := time.Now().UnixNano()

	var (
		overall  int64 = 0
		succeeds int   = 0
		errors   int   = 0

		dns_errors   int = 0
		sock_errors  int = 0
		read_errors  int = 0
		write_errors int = 0
		svr_errors   int = 0

		avg        float32
		rps        float32
		time_spent float32
	)
	for i := 0; i < requests; i++ {
		result := <-results
		if result < 0 {
			errors += 1
			switch result {
			case -1:
				dns_errors += 1
			case -2:
				sock_errors += 1
			case -3:
				write_errors += 1
			case -4:
				read_errors += 1
			case -5:
				svr_errors += 1
			}
		} else {
			overall += result
			succeeds += 1
		}
	}

	if succeeds > 0 {
		avg = float32(overall) / float32(succeeds)
	} else {
		avg = 0
	}
	time_spent = float32(finish-start) / 1e+9 // in sec.
	rps = float32(requests) / float32(time_spent)

	fmt.Printf("Errors: %d, Succeeds: %d\n", errors, succeeds)
	fmt.Printf("DNS: %d, Socket: %d, Write: %d, Read: %d, Server: %d\n",
		dns_errors, sock_errors, write_errors, read_errors, svr_errors)
	fmt.Printf("Response time (avg.): %f ms\n", avg)
	fmt.Printf("Requests per second (avg.): %f req/s\n", rps)
	fmt.Printf("Time spent: %f s\n", time_spent)
	os.Exit(0)
}
