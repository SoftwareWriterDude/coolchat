package main

//  cool chat server

/*  This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"strings"
	"sync"
	"time"
	"unicode"
    "log"
    "crypto/rand"
    "crypto/tls"
    "crypto/rsa"
    "crypto/x509"
    "crypto/x509/pkix"
    "encoding/pem"
    "math/big"
)

var (
	clients     = make(map[string]*clientInfo) // Map to store username -> clientInfo
	clientsLock sync.Mutex
)

type clientInfo struct {
	conn         net.Conn
	messageCount int
	lastMessage  time.Time
}

const (
	maxMessagesPerSecond = 1    // Maximum allowed messages per second
	messageTimeWindow    = 5   // Time window in seconds to count messages
	kickThreshold        = 2   // Maximum allowed messages within the window before kicking the client
	kickDuration         = 60   // Duration in seconds for which the client is kicked
	maxClients           = 100  // Max clients allowed to connect
	maxUsernameLen       = 20 // max username length
)

func filterNoise(input string) bool {
    // Convert input and search terms to lowercase for case-insensitive comparison
    inputLower := strings.ToLower(input)
    httpLower := "http"
    connectLower := "connect"

    // Check if either "http" or "connect" exists in the input string
    if strings.Contains(inputLower, httpLower) || strings.Contains(inputLower, connectLower) {
        return true
    }
    return false
}

func hasNonASCIIChars(s string) bool {
    for _, char := range s {
        if char > 127 {
            return true
        }
    }
    return false
}

func removeColon(input string) string {
    var output strings.Builder

    for _, char := range input {
        if char != ':' {
            output.WriteRune(char)
        }
    }
    return output.String()
}

func truncateString(input string, length int) string {
    // Ensure length is within the bounds of the string
    if length > len(input) {
        length = len(input)
    }

    return input[:length]
}

func removeSpaces(input string) string {
    var output string
    for _, char := range input {
        if !unicode.IsSpace(char) {
            output += string(char)
        }
    }

    return output
}

func getUsername(client net.Conn) {

    var username string
    var problem bool
    
    
    clientAddress := client.RemoteAddr().String()
    //fmt.Printf("New connection from %s\n", clientAddress)

    // Send the number of connected users to the client
    clientsLock.Lock()
    numConnected := len(clients)
    clientsLock.Unlock()
    if numConnected > maxClients {
        client.Write([]byte("The server is currently at max capacity, try again later."))
        client.Close()
        return
    }
    
    // send MOTD
    client.Write([]byte(fmt.Sprintf("Welcome to Cool chat\nCurrently %d user(s) are connected.", numConnected)))

    client.Write([]byte(fmt.Sprintf("Your ip appears to be: %s\n", clientAddress)))

    for {

        problem = false
        
        // Prompt the client for a username
        client.Write([]byte("Please enter your username: "))

        // Set a timer for the username entry timeout
        usernameTimer := time.NewTimer(30 * time.Second)

        // Receive the username with a goroutine to handle the timeout
        usernameChan := make(chan string)
        go func() {

            username, err := bufio.NewReader(client).ReadString('\n')
            if err != nil {
                //fmt.Printf("Failed to receive username from %s: %s\n", clientAddress, err)
                client.Close()
                return
            }

            if filterNoise(username) == true {
                client.Close()
                return
            }

			//fmt.Printf(fmt.Sprintf("%s", username))
            username = strings.TrimSpace(username) // Remove leading/trailing spaces, tabs, and newlines
            username = removeColon(username)
            username = removeSpaces(username)
            username = truncateString(username, maxUsernameLen)
    
            if len(username) > 1 && hasNonASCIIChars(username) == false {
                usernameChan <- username
            } else {
                client.Write([]byte(fmt.Sprintf("Don't send non-ascii chars and username must be len > 1\n")))
                problem = true
            }

        }()

        // Wait for either the username or timeout
        select {
            case <-usernameTimer.C:
                client.Write([]byte("\r\r\nUsername entry timed out. Disconnecting...\n"))
                client.Close()
                return
            case username = <-usernameChan:
                usernameTimer.Stop()
        }

        // Check if the username is already in use
        clientsLock.Lock()
        if _, exists := clients[username]; exists {
            client.Write([]byte("Username already in use. Please choose a different username.\n"))
            clientsLock.Unlock()
            problem = true
        }

        if problem == false {
            break
        }
       
    }// end loop

    clients[username] = &clientInfo{conn: client}
    clientsLock.Unlock()

    // handle the client with a go routine
    go handleClient(client, username)
    
}

func handleClient(client net.Conn, username string) {

    client.Write([]byte(fmt.Sprintf("Welcome %s, You may now begin chatting.", username)))
    broadcast(fmt.Sprintf("%s %s", username, "Has joined the chat."))

    // Start handling messages from the client
    for {
        message, err := bufio.NewReader(client).ReadString('\n')
        if err != nil {
            //fmt.Printf("Error occurred with %s: %s\n", clientAddress, err)
            broadcast(fmt.Sprintf("%s %s", username, "Has left the chat."))
            break
        }

        message = strings.Map(func(r rune) rune {
            // Filter out tab and newline characters
            if r == '\t' || r == '\n' || r == '\r' {
                return -1
            }
            return r
        }, message)

        if len(message) == 0 {
            client.Write([]byte("Don't send newline tab or carraige return characters."))
            break
        }

        clientsLock.Lock()
        clientInfo := clients[username]
        clientsLock.Unlock()

        // Check for message rate limiting
        if clientInfo != nil {
            now := time.Now()
            if now.Sub(clientInfo.lastMessage) >= time.Second {
                // Reset message count and update last message time
                clientInfo.messageCount = 1
                clientInfo.lastMessage = now
            } else {
                clientInfo.messageCount++
                if clientInfo.messageCount > kickThreshold {
                    //client.Write([]byte("You have been kicked due to message flooding. Please wait and reconnect.\r\r\n"))
					broadcast(fmt.Sprintf("%s %s", username, "was kicked for flooding."))
                    //time.Sleep(kickDuration * time.Second)
                    client.Close()

                    clientsLock.Lock()
                    delete(clients, username)
                    clientsLock.Unlock()

                    //fmt.Printf("Kicked %s due to message flooding\n", username)
                    break
                }
            }
        }

        //fmt.Printf("Received message from %s - %s: %s\n", clientAddress, username, message)

		if hasNonASCIIChars(message) == false {
			broadcast(fmt.Sprintf("%s: %s", username, message))
		}
    }

    // Remove the client from the map when the connection is closed
    clientsLock.Lock()
    delete(clients, username)
    clientsLock.Unlock()

    // Close the client connection
    client.Close()
    //fmt.Printf("Connection closed with %s\n", clientAddress)
}



func broadcast(message string) {
	clientsLock.Lock()
	defer clientsLock.Unlock()

	disconnectedClients := []string{}
	for username, clientInfo := range clients {
		_, err := clientInfo.conn.Write([]byte(message))
		if err != nil {
			//fmt.Printf("Error occurred while broadcasting to %s (%s): %s\n", username, clientInfo.conn.RemoteAddr().String(), err)
			clientInfo.conn.Close()
			disconnectedClients = append(disconnectedClients, username)
		}
	}

	// Remove disconnected clients from the map
	for _, username := range disconnectedClients {
		delete(clients, username)
	}
}

func generateCertificate(orgName string) error {
	// Generate RSA private key
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return fmt.Errorf("failed to generate private key: %v", err)
	}

	// Generate certificate template
	template := x509.Certificate {
		SerialNumber:          big.NewInt(1),
		Subject:               pkix.Name{Organization: []string{orgName}},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(365 * 24 * time.Hour),
		KeyUsage:              x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
	}

	// Create a self-signed certificate
	derBytes, err := x509.CreateCertificate(rand.Reader, &template, &template, &privateKey.PublicKey, privateKey)
	if err != nil {
		return fmt.Errorf("failed to create certificate: %v", err)
	}

	// Write private key to file
	keyFile, err := os.Create("server.key")
	if err != nil {
		return fmt.Errorf("failed to create private key file: %v", err)
	}
	defer keyFile.Close()
	keyBlock := &pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(privateKey)}
	if err := pem.Encode(keyFile, keyBlock); err != nil {
		return fmt.Errorf("failed to write private key to file: %v", err)
	}

	// Write certificate to file
	certFile, err := os.Create("server.crt")
	if err != nil {
		return fmt.Errorf("failed to create certificate file: %v", err)
	}
	defer certFile.Close()
	certBlock := &pem.Block{Type: "CERTIFICATE", Bytes: derBytes}
	if err := pem.Encode(certFile, certBlock); err != nil {
		return fmt.Errorf("failed to write certificate to file: %v", err)
	}

	fmt.Println("Certificate and private key generated successfully.\n")
	return nil
}


func main() {

    var orgName string
	var answer string
	scanner := bufio.NewScanner(os.Stdin)

	if len(os.Args) == 2 {
		if len(os.Args[1]) > 0 && os.Args[1] == "gencert" {
			fmt.Print("This will overwrite existing certs. Continue (y/n)?: ")
			fmt.Scanln(&answer)
			if answer != "y" {
				os.Exit(0)
			}
			fmt.Print("Organization name: ")
			scanner.Scan()
			orgName = scanner.Text()
			if len(orgName) > 2 {
				err := generateCertificate(orgName)
				if err != nil {
					fmt.Printf("Error: %v\n", err)
					os.Exit(1)
				}
			}
		}
		os.Exit(0)
	}

	if len(os.Args) != 3 {
		fmt.Printf("Usage: %s <host> <port>\n", os.Args[0])
		os.Exit(0)
	}

	hostport := os.Args[1] + ":" + os.Args[2]

	// Load SSL/TLS certificates
	cert, err := tls.LoadX509KeyPair("server.crt", "server.key")
	if err != nil {
		log.Fatalf("failed to load certificates: %v", err)
        fmt.Printf("Error loading certificates.\n")
        os.Exit(1)
	}

	// Create TLS configuration
	config := &tls.Config{
		Certificates: []tls.Certificate{cert},
	}

	// Listen for incoming SSL/TLS connections
	listener, err := tls.Listen("tcp", hostport, config)
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	defer listener.Close()

	fmt.Println(fmt.Sprintf("Server is listening for incoming SSL/TLS connections on %s", hostport))

	for {
		// Accept incoming connections
		conn, err := listener.Accept()
		if err != nil {
			log.Printf("failed to accept connection: %v", err)
			continue
		}

		fmt.Println("Client connected over SSL/TLS.")

		// Handle connections concurrently
		go getUsername(conn)
	}
}

