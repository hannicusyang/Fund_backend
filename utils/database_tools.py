"""

UPDATE fund_estimation
SET
    estimation_date = CURDATE(),
    fetch_time = CONCAT(CURDATE(), ' ', TIME(fetch_time));


"""