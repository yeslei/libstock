export type EmployeeAccessLevel = 'SELLER' | 'STOCK_KEEPER' | 'ADMINISTRATOR';

export interface CreateEmployeeRequest {
  name: string;
  email: string;
  password: string;
  accessLevel: EmployeeAccessLevel;
}

export interface CreateEmployeeResponse {
  readonly id: number;
  readonly name: string;
  readonly email: string;
  readonly role_code: EmployeeAccessLevel;
}
