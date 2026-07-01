function doPost(e) {
  var ss = SpreadsheetApp.openById('1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80');
  var raw = (e.postData && e.postData.contents) ? e.postData.contents : '{}';
  var d = JSON.parse(raw);

  // ── LIKES TAB ──────────────────────────────────────────────────────
  if (d.action === 'like') {
    var likesSheet = ss.getSheetByName('Website Likes');
    if (!likesSheet) {
      likesSheet = ss.insertSheet('Website Likes');
      likesSheet.appendRow(['Timestamp', 'Action']);
      likesSheet.setFrozenRows(1);
    }
    likesSheet.appendRow([d.timestamp || new Date(), 'Like']);
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── GOOGLE SIGN-IN LOG ───────────────────────────────────────────
  if (d.action === 'googleSignIn') {
    var usersSheet = ss.getSheetByName('User Accounts');
    if (!usersSheet) {
      usersSheet = ss.insertSheet('User Accounts');
      usersSheet.appendRow(['Timestamp', 'Full Name', 'Email', 'Sign-In Method']);
      usersSheet.setFrozenRows(1);
    }
    var email = (d.email || '').trim().toLowerCase();
    var name = d.name || '';
    // Check if user already exists — if not, add them
    var data = usersSheet.getDataRange().getValues();
    var exists = false;
    for (var i = 1; i < data.length; i++) {
      if ((data[i][2] || '').trim().toLowerCase() === email) {
        exists = true;
        break;
      }
    }
    if (!exists) {
      usersSheet.appendRow([new Date(), name, email, 'Google']);
    }
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── SEND OTP ───────────────────────────────────────────────────────
  if (d.action === 'sendOTP') {
    var email = (d.email || '').trim().toLowerCase();
    if (!email) {
      return ContentService.createTextOutput(JSON.stringify({status:'error', message:'Email is required'})).setMimeType(ContentService.MimeType.JSON);
    }

    // Get or create OTP sheet
    var otpSheet = ss.getSheetByName('OTP');
    if (!otpSheet) {
      otpSheet = ss.insertSheet('OTP');
      otpSheet.appendRow(['Email', 'Code', 'CreatedAt', 'ExpiresAt', 'Used']);
      otpSheet.setFrozenRows(1);
    }

    // Rate limit: max 3 OTPs per email per hour
    var now = new Date();
    var oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    var otpData = otpSheet.getDataRange().getValues();
    var recentCount = 0;
    for (var i = 1; i < otpData.length; i++) {
      if ((otpData[i][0] || '').toLowerCase() === email) {
        var created = new Date(otpData[i][2]);
        if (created > oneHourAgo) recentCount++;
      }
    }
    if (recentCount >= 3) {
      return ContentService.createTextOutput(JSON.stringify({status:'error', message:'Too many OTP requests. Please wait and try again later.'})).setMimeType(ContentService.MimeType.JSON);
    }

    // Generate 4-digit OTP
    var otp = String(Math.floor(1000 + Math.random() * 9000));
    var expiresAt = new Date(now.getTime() + 5 * 60 * 1000); // 5 minutes

    // Store OTP
    otpSheet.appendRow([email, otp, now, expiresAt, false]);

    // Send email
    var subject = 'The Furever Home — Your Login Code';
    var body = 'Hi there! 🐾\n\n'
      + 'Your one-time login code for The Furever Home is:\n\n'
      + '    ' + otp + '\n\n'
      + 'This code expires in 5 minutes.\n'
      + 'If you did not request this, please ignore this email.\n\n'
      + '— The Furever Home Team\n'
      + 'https://the-furever-home.com';

    try {
      MailApp.sendEmail(email, subject, body);
    } catch (mailErr) {
      return ContentService.createTextOutput(JSON.stringify({status:'error', message:'Failed to send email. Please check your email address.'})).setMimeType(ContentService.MimeType.JSON);
    }

    // Check if this is an existing user
    var usersSheet = ss.getSheetByName('User Accounts');
    var isExisting = false;
    if (usersSheet) {
      var userData = usersSheet.getDataRange().getValues();
      for (var j = 1; j < userData.length; j++) {
        if ((userData[j][2] || '').trim().toLowerCase() === email) {
          isExisting = true;
          break;
        }
      }
    }

    return ContentService.createTextOutput(JSON.stringify({status:'ok', isExisting: isExisting})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── VERIFY OTP ─────────────────────────────────────────────────────
  if (d.action === 'verifyOTP') {
    var email = (d.email || '').trim().toLowerCase();
    var code = (d.code || '').trim();

    if (!email || !code) {
      return ContentService.createTextOutput(JSON.stringify({status:'error', message:'Email and code are required'})).setMimeType(ContentService.MimeType.JSON);
    }

    var otpSheet = ss.getSheetByName('OTP');
    if (!otpSheet) {
      return ContentService.createTextOutput(JSON.stringify({status:'error', message:'No OTP found. Please request a new code.'})).setMimeType(ContentService.MimeType.JSON);
    }

    var now = new Date();
    var otpData = otpSheet.getDataRange().getValues();
    var validOtp = false;
    var otpRowIndex = -1;

    // Search for matching, unused, non-expired OTP (most recent first)
    for (var i = otpData.length - 1; i >= 1; i--) {
      if ((otpData[i][0] || '').toLowerCase() === email && String(otpData[i][1]) === code) {
        var expiresAt = new Date(otpData[i][3]);
        var used = otpData[i][4];
        if (!used && now < expiresAt) {
          validOtp = true;
          otpRowIndex = i + 1; // Sheet rows are 1-indexed
          break;
        }
      }
    }

    if (!validOtp) {
      return ContentService.createTextOutput(JSON.stringify({status:'error', message:'Invalid or expired code. Please try again or request a new one.'})).setMimeType(ContentService.MimeType.JSON);
    }

    // Mark OTP as used
    otpSheet.getRange(otpRowIndex, 5).setValue(true);

    // Check if user exists
    var usersSheet = ss.getSheetByName('User Accounts');
    if (!usersSheet) {
      usersSheet = ss.insertSheet('User Accounts');
      usersSheet.appendRow(['Timestamp', 'Full Name', 'Email']);
      usersSheet.setFrozenRows(1);
    }

    var userData = usersSheet.getDataRange().getValues();
    var existingUser = null;
    for (var j = 1; j < userData.length; j++) {
      if ((userData[j][2] || '').trim().toLowerCase() === email) {
        existingUser = { name: userData[j][1], email: userData[j][2] };
        break;
      }
    }

    if (existingUser) {
      // Existing user — return their info
      return ContentService.createTextOutput(JSON.stringify({status:'ok', isNew: false, name: existingUser.name, email: existingUser.email})).setMimeType(ContentService.MimeType.JSON);
    } else {
      // New user — needs name
      var name = (d.name || '').trim();
      if (name) {
        // They provided a name — create account
        usersSheet.appendRow([new Date(), name, email]);
        return ContentService.createTextOutput(JSON.stringify({status:'ok', isNew: false, name: name, email: email})).setMimeType(ContentService.MimeType.JSON);
      } else {
        // Ask frontend to collect name
        return ContentService.createTextOutput(JSON.stringify({status:'ok', isNew: true, email: email})).setMimeType(ContentService.MimeType.JSON);
      }
    }
  }

  // ── SHOWN INTEREST TAB ─────────────────────────────────────────────
  if (d.action === 'shownInterest') {
    var interestSheet = ss.getSheetByName('Shown Interest');
    if (!interestSheet) {
      interestSheet = ss.insertSheet('Shown Interest');
      interestSheet.appendRow(['Pet Name', 'Pet ID', 'Breed', 'Shelter Name', 'Shelter URL', 'Date', 'Time', 'User Name', 'User Email']);
      interestSheet.setFrozenRows(1);
    }
    interestSheet.appendRow([d.petName, d.petId, d.breed, d.shelterName, d.shelterUrl, d.date, d.time, d.userName, d.userEmail]);
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── ADOPTION INQUIRIES TAB ─────────────────────────────────────────
  var sheet = ss.getSheetByName('Inquiries');
  if (!sheet) {
    sheet = ss.insertSheet('Inquiries');
    sheet.appendRow(['Timestamp','Pet ID','Pet Name','Breed','Shelter','First Name','Last Name','Email','Phone','City','Housing Type','Pet Experience','Message']);
    sheet.setFrozenRows(1);
  }
  sheet.appendRow([new Date(), d.petId||'', d.petName||'', d.breed||'', d.shelter||'', d.firstName||'', d.lastName||'', d.email||'', d.phone||'', d.city||'', d.housing||'', d.experience||'', d.message||'']);
  return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
}
