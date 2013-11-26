package main

import (
	"encoding/binary"
	"fmt"
	"net"
	"os"
	"time"
)

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
	var worker = 1024
	semaphore := make(chan int, worker)

	// Launch
	for i := 0; i < worker; i++ {
		go func() {
			send_request()
			semaphore <- 1;
		}()
	}

	// Wait for goroutines to complete
	for i := 0; i < worker; i++ { <- semaphore }

	os.Exit(0)
}
