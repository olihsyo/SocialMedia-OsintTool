<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$action = $_GET['action'] ?? '';

function req($url, $method = 'GET', $data = null, $token = null) {
    $opts = [
        'http' => [
            'method' => $method,
            'header' => "Content-Type: application/json\r\nAccept: application/json\r\n",
            'timeout' => 10,
            'ignore_errors' => true
        ],
        'ssl' => ['verify_peer' => false, 'verify_peer_name' => false]
    ];
    if ($token) $opts['http']['header'] .= "Authorization: Bearer $token\r\n";
    if ($data) $opts['http']['content'] = json_encode($data);
    $ctx = stream_context_create($opts);
    $res = @file_get_contents($url, false, $ctx);
    return $res ? json_decode($res, true) : null;
}

$api = 'https://api.mail.gw';

if ($action === 'generate') {
    $domains = req("$api/domains");
    if (!$domains) { echo json_encode(['error' => 'API offline']); exit; }
    $domain = $domains['hydra:member'][0]['domain'];
    $email = 'user_' . rand(1000, 9999) . '@' . $domain;
    $pass = 'Pass' . rand(10000, 99999);
    
    $acc = req("$api/accounts", 'POST', ['address' => $email, 'password' => $pass]);
    if (!$acc) { echo json_encode(['error' => 'Account failed']); exit; }
    
    $login = req("$api/token", 'POST', ['address' => $email, 'password' => $pass]);
    if (!$login) { echo json_encode(['error' => 'Login failed']); exit; }
    
    echo json_encode(['email' => $email, 'token' => $login['token']]);
}

if ($action === 'inbox') {
    $token = $_GET['token'] ?? '';
    $messages = req("$api/messages", 'GET', null, $token);
    if (!$messages) { echo json_encode([]); exit; }
    echo json_encode($messages['hydra:member'] ?? []);
}

if ($action === 'message') {
    $token = $_GET['token'] ?? '';
    $id = $_GET['id'] ?? '';
    $msg = req("$api/messages/$id", 'GET', null, $token);
    echo json_encode($msg);
}
